"""UpbitExchange — 업비트 REST 주문·잔고 (live 모드) (CHECKLIST 4.4~4.10).

- JWT 서명 인증 (4.10)
- 시장가 매수/매도 (4.5), 잔고·현재가 조회 (4.4)
- 재시도 3회 지수 백오프 (4.7), Rate limit 준수 (4.8)
"""

from __future__ import annotations

import hashlib
import logging
import math
import time
import urllib.parse
from typing import Any, Callable
from uuid import uuid4

import jwt
import requests

from .. import constants
from .base import Balance, OrderResult, OrderSide

log = logging.getLogger(__name__)

_BASE = constants.UPBIT_REST_BASE


class UpbitAPIError(RuntimeError):
    """업비트 API 통신·인증 오류 (3회 재시도 실패 포함)."""


def _retry(fn: Callable[[], Any], *, max_retries: int = constants.UPBIT_MAX_RETRIES) -> Any:
    """지수 백오프 재시도. 마지막 실패 시 UpbitAPIError 발생 (4.7)."""
    last_exc: Exception | None = None
    for attempt in range(max_retries):
        try:
            return fn()
        except (requests.RequestException, UpbitAPIError) as exc:
            last_exc = exc
            if attempt < max_retries - 1:
                time.sleep(0.5 * (2 ** attempt))  # 0.5s, 1s, 2s
    raise UpbitAPIError(f"업비트 API {max_retries}회 재시도 실패: {last_exc}") from last_exc


class UpbitExchange:
    """업비트 실거래 게이트웨이."""

    def __init__(
        self,
        access_key: str,
        secret_key: str,
        market: str = constants.MARKET,
        session: requests.Session | None = None,
        order_type: str = constants.ORDER_TYPE_MARKET,
        limit_wait_seconds: float = constants.LIMIT_ORDER_WAIT_SECONDS,
        limit_offset_bp: float = constants.LIMIT_ORDER_OFFSET_BP,
    ) -> None:
        if not access_key or not secret_key:
            raise ValueError("Upbit API 키가 비어 있습니다 (인증 불가)")
        self.access_key = access_key
        self.secret_key = secret_key
        self.market = market
        self._session = session or requests.Session()
        self._last_call = 0.0
        self.order_type = order_type
        self.limit_wait_seconds = limit_wait_seconds
        self.limit_offset_bp = limit_offset_bp

    # --- 인증 -----------------------------------------------------------------
    def _auth_header(self, params: dict[str, Any] | None = None) -> dict[str, str]:
        payload: dict[str, Any] = {"access_key": self.access_key, "nonce": uuid4().hex}
        if params:
            query = urllib.parse.urlencode(params, doseq=True)
            query_hash = hashlib.sha512(query.encode()).hexdigest()
            payload["query_hash"] = query_hash
            payload["query_hash_alg"] = "SHA512"
        token = jwt.encode(payload, self.secret_key, algorithm="HS256")
        return {"Authorization": f"Bearer {token}"}

    def _rate_limit(self) -> None:
        """초당 호출 상한 준수 (4.8)."""
        min_interval = 1.0 / constants.UPBIT_RATE_LIMIT_PER_SEC
        elapsed = time.monotonic() - self._last_call
        if elapsed < min_interval:
            time.sleep(min_interval - elapsed)
        self._last_call = time.monotonic()

    # --- 조회 -----------------------------------------------------------------
    def get_price(self, market: str) -> float:
        def call() -> float:
            self._rate_limit()
            resp = self._session.get(
                f"{_BASE}/v1/ticker", params={"markets": market}, timeout=10
            )
            resp.raise_for_status()
            return float(resp.json()[0]["trade_price"])

        return _retry(call)

    def get_balance(self) -> Balance:
        def call() -> Balance:
            self._rate_limit()
            resp = self._session.get(
                f"{_BASE}/v1/accounts", headers=self._auth_header(), timeout=10
            )
            resp.raise_for_status()
            krw = btc = krw_locked = btc_locked = 0.0
            for acc in resp.json():
                if acc["currency"] == "KRW":
                    krw = float(acc["balance"])
                    krw_locked = float(acc.get("locked", 0.0))
                elif acc["currency"] == "BTC":
                    btc = float(acc["balance"])
                    btc_locked = float(acc.get("locked", 0.0))
            return Balance(krw=krw, btc=btc, krw_locked=krw_locked, btc_locked=btc_locked)

        return _retry(call)

    # --- 주문 (공개 진입점) ---------------------------------------------------
    def buy_market(self, market: str, price: float, quantity: float) -> OrderResult:
        """매수. order_type=limit 이면 종가 근처 지정가 후 미체결분은 시장가 폴백(#3)."""
        if self.order_type == constants.ORDER_TYPE_LIMIT:
            return self._buy_limit_then_market(market, price, quantity)
        return self._buy_market(market, price, quantity)

    def sell_market(self, market: str, price: float, quantity: float) -> OrderResult:
        """매도. order_type=limit 이면 지정가 후 미체결분은 시장가 폴백(#3)."""
        if self.order_type == constants.ORDER_TYPE_LIMIT:
            return self._sell_limit_then_market(market, price, quantity)
        return self._sell_market(market, price, quantity)

    # --- 시장가 -----------------------------------------------------------------
    def _buy_market(self, market: str, price: float, quantity: float) -> OrderResult:
        """시장가 매수(원화마켓은 총액 지정). 실체결가·수량·수수료를 반영."""
        funds, vol, fee, uuid = self._market_buy_fills(market, price, quantity)
        fill_price = funds / vol
        _log_slippage("매수", price, fill_price)
        return OrderResult(
            ok=True, side=OrderSide.BUY, market=market,
            price=fill_price, quantity=vol, fee=fee, order_id=uuid,
            reason="업비트 매수 체결",
        )

    def _sell_market(self, market: str, price: float, quantity: float) -> OrderResult:
        funds, vol, fee, uuid = self._market_sell_fills(market, price, quantity)
        fill_price = funds / vol
        _log_slippage("매도", price, fill_price)
        return OrderResult(
            ok=True, side=OrderSide.SELL, market=market,
            price=fill_price, quantity=vol, fee=fee, order_id=uuid,
            reason="업비트 매도 체결",
        )

    def _market_buy_fills(
        self, market: str, price: float, quantity: float
    ) -> tuple[float, float, float, str]:
        """시장가 매수 접수 후 (체결대금, 체결수량, 수수료, uuid).

        체결 내역을 확인 못하면 요청가로 폴백한다(주문은 접수됐으므로 상태 일관성 우선).
        """
        total_krw = round(price * quantity)
        data = self._order({
            "market": market, "side": "bid",
            "ord_type": "price", "price": str(total_krw),
        })
        uuid = data.get("uuid", "")
        detail = self._poll(uuid, constants.UPBIT_ORDER_SETTLE_POLLS)
        funds, vol, fee = _extract_fills(detail)
        if vol <= 0:
            vol = float(detail.get("executed_volume") or 0.0) or quantity
            funds = price * vol
            log.warning("매수 체결 내역 미확보(uuid=%s) — 요청가 폴백", uuid)
        return funds, vol, fee, uuid

    def _market_sell_fills(
        self, market: str, price: float, quantity: float
    ) -> tuple[float, float, float, str]:
        data = self._order({
            "market": market, "side": "ask",
            "ord_type": "market", "volume": _fmt_volume(quantity),
        })
        uuid = data.get("uuid", "")
        detail = self._poll(uuid, constants.UPBIT_ORDER_SETTLE_POLLS)
        funds, vol, fee = _extract_fills(detail)
        if vol <= 0:
            vol = float(detail.get("executed_volume") or 0.0) or quantity
            funds = price * vol
            log.warning("매도 체결 내역 미확보(uuid=%s) — 요청가 폴백", uuid)
        return funds, vol, fee, uuid

    # --- 지정가 + 시장가 폴백 (#3) ---------------------------------------------
    def _buy_limit_then_market(
        self, market: str, price: float, quantity: float
    ) -> OrderResult:
        limit_price = _round_to_tick(price * (1 - self.limit_offset_bp / 10_000), OrderSide.BUY)
        data = self._order({
            "market": market, "side": "bid", "ord_type": "limit",
            "price": _fmt_price(limit_price), "volume": _fmt_volume(quantity),
        })
        uuid = data.get("uuid", "")
        l_funds, l_vol, l_fee = self._wait_limit(uuid)
        remaining = quantity - l_vol

        m_funds = m_vol = m_fee = 0.0
        if remaining * price >= _MIN_ORDER_KRW:
            log.info("지정가 미체결분 %.8f BTC → 시장가 폴백", remaining)
            m_funds, m_vol, m_fee, _ = self._market_buy_fills(market, price, remaining)

        return self._combine(
            OrderSide.BUY, market, price, uuid,
            l_funds + m_funds, l_vol + m_vol, l_fee + m_fee, l_vol, m_vol,
        )

    def _sell_limit_then_market(
        self, market: str, price: float, quantity: float
    ) -> OrderResult:
        limit_price = _round_to_tick(price * (1 + self.limit_offset_bp / 10_000), OrderSide.SELL)
        data = self._order({
            "market": market, "side": "ask", "ord_type": "limit",
            "price": _fmt_price(limit_price), "volume": _fmt_volume(quantity),
        })
        uuid = data.get("uuid", "")
        l_funds, l_vol, l_fee = self._wait_limit(uuid)
        remaining = quantity - l_vol

        m_funds = m_vol = m_fee = 0.0
        if remaining * price >= _MIN_ORDER_KRW:
            log.info("지정가 미체결분 %.8f BTC → 시장가 폴백", remaining)
            m_funds, m_vol, m_fee, _ = self._market_sell_fills(market, price, remaining)

        return self._combine(
            OrderSide.SELL, market, price, uuid,
            l_funds + m_funds, l_vol + m_vol, l_fee + m_fee, l_vol, m_vol,
        )

    def _wait_limit(self, uuid: str) -> tuple[float, float, float]:
        """지정가 접수 후 limit_wait_seconds 까지 대기. 미체결 시 취소하고 체결분만 반환."""
        polls = max(1, int(self.limit_wait_seconds / constants.UPBIT_ORDER_SETTLE_INTERVAL))
        detail = self._poll(uuid, polls)
        if detail.get("state") != "done":
            try:
                self.cancel_order(uuid)
            except UpbitAPIError as exc:
                log.warning("지정가 취소 실패(uuid=%s): %s", uuid, exc)
            detail = self._poll(uuid, constants.UPBIT_ORDER_SETTLE_POLLS)  # 취소 반영 대기
        return _extract_fills(detail)

    def _combine(
        self, side: OrderSide, market: str, req_price: float, uuid: str,
        funds: float, vol: float, fee: float, l_vol: float, m_vol: float,
    ) -> OrderResult:
        if vol <= 0:
            return OrderResult(
                ok=False, side=side, market=market, price=req_price,
                quantity=0.0, order_id=uuid, reason="지정가·시장가 모두 미체결",
            )
        avg = funds / vol
        label = "매수" if side is OrderSide.BUY else "매도"
        log.info("%s 지정가 %.8f + 시장가 %.8f BTC 체결", label, l_vol, m_vol)
        _log_slippage(label, req_price, avg)
        return OrderResult(
            ok=True, side=side, market=market, price=avg, quantity=vol, fee=fee,
            order_id=uuid, reason=f"업비트 {label} 체결(지정가+폴백)",
        )

    # --- 체결 조회 헬퍼 --------------------------------------------------------
    def _poll(self, uuid: str, polls: int) -> dict[str, Any]:
        """get_order 를 state 가 done/cancel 이 되거나 상한까지 폴링해 마지막 응답 반환."""
        data: dict[str, Any] = {}
        for attempt in range(polls):
            try:
                data = self.get_order(uuid)
            except UpbitAPIError as exc:
                log.warning("체결 조회 실패(%d회차): %s", attempt + 1, exc)
                break
            if data.get("state") in ("done", "cancel"):
                break
            if attempt < polls - 1:
                time.sleep(constants.UPBIT_ORDER_SETTLE_INTERVAL)
        return data

    def cancel_order(self, uuid: str) -> dict[str, Any]:
        """미체결 주문 취소 (DELETE /v1/order)."""
        params = {"uuid": uuid}

        def call() -> dict[str, Any]:
            self._rate_limit()
            resp = self._session.delete(
                f"{_BASE}/v1/order", params=params,
                headers=self._auth_header(params), timeout=10,
            )
            if resp.status_code >= 400:
                raise UpbitAPIError(f"주문 취소 실패 {resp.status_code}: {resp.text}")
            return resp.json()

        return _retry(call)

    def _order(self, params: dict[str, Any]) -> dict[str, Any]:
        def call() -> dict[str, Any]:
            self._rate_limit()
            resp = self._session.post(
                f"{_BASE}/v1/orders",
                params=params,
                headers=self._auth_header(params),
                timeout=10,
            )
            if resp.status_code >= 400:
                raise UpbitAPIError(f"주문 실패 {resp.status_code}: {resp.text}")
            return resp.json()

        return _retry(call)

    def get_order(self, uuid: str) -> dict[str, Any]:
        """주문 상태 조회 (4.6)."""
        params = {"uuid": uuid}

        def call() -> dict[str, Any]:
            self._rate_limit()
            resp = self._session.get(
                f"{_BASE}/v1/order", params=params,
                headers=self._auth_header(params), timeout=10,
            )
            resp.raise_for_status()
            return resp.json()

        return _retry(call)


_MIN_ORDER_KRW = 5000  # 업비트 원화마켓 최소 주문 금액


def _extract_fills(detail: dict[str, Any]) -> tuple[float, float, float]:
    """주문 상세의 trades[]에서 (체결대금 funds, 체결수량 volume, 수수료 paid_fee)."""
    trades = detail.get("trades") or []
    funds = sum(float(t["funds"]) for t in trades)
    vol = sum(float(t["volume"]) for t in trades)
    fee = float(detail.get("paid_fee") or 0.0)
    return funds, vol, fee


def _tick_size(price: float) -> float:
    """업비트 원화마켓 호가 단위(가격대별). KRW-BTC(수백만~) 기준 1000원."""
    if price >= 2_000_000:
        return 1000.0
    if price >= 1_000_000:
        return 500.0
    if price >= 500_000:
        return 100.0
    if price >= 100_000:
        return 50.0
    if price >= 10_000:
        return 10.0
    if price >= 1_000:
        return 1.0
    if price >= 100:
        return 0.1
    if price >= 10:
        return 0.01
    if price >= 1:
        return 0.001
    if price >= 0.1:
        return 0.0001
    return 0.00001


def _round_to_tick(price: float, side: OrderSide) -> float:
    """호가 단위로 정렬. 매수는 내림(≤요청가), 매도는 올림(≥요청가)으로 불리하지 않게."""
    tick = _tick_size(price)
    if side is OrderSide.BUY:
        return math.floor(price / tick) * tick
    return math.ceil(price / tick) * tick


def _fmt_price(price: float) -> str:
    """지정가 문자열. 정수 틱이면 정수로, 소액 틱이면 소수 유지."""
    if price == int(price):
        return str(int(price))
    return f"{price:.8f}".rstrip("0").rstrip(".")


def _fmt_volume(qty: float) -> str:
    return f"{qty:.8f}".rstrip("0").rstrip(".")


def _log_slippage(label: str, req_price: float, fill_price: float) -> None:
    """요청가 대비 실제 체결가 차이(슬리피지)를 bp 단위로 기록."""
    if req_price <= 0:
        return
    bp = (fill_price - req_price) / req_price * 10_000
    log.info(
        "%s 슬리피지 %+.1fbp (요청 %s → 체결 %s)",
        label, bp, f"{req_price:,.0f}", f"{fill_price:,.0f}",
    )
