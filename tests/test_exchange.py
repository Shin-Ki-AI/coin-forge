"""UpbitExchange 실체결가 반영 테스트 (슬리피지 측정).

시장가 주문 접수 후 get_order 폴링으로 실제 평균 체결가·수량·수수료를
OrderResult 에 반영하는지 검증한다. 실제 네트워크 없이 세션을 스텁으로 대체.
"""

from __future__ import annotations

import pytest

from coinforge.exchange import upbit as upbit_mod
from coinforge.exchange.base import OrderSide
from coinforge.exchange.mock import MockExchange
from coinforge.exchange.upbit import UpbitExchange


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch):
    """네트워크가 스텁이므로 재시도·폴링 대기를 제거해 테스트를 빠르게."""
    monkeypatch.setattr(upbit_mod.time, "sleep", lambda *_: None)


class _FakeResp:
    def __init__(self, payload, status: int = 200) -> None:
        self._payload = payload
        self.status_code = status
        self.text = str(payload)

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise AssertionError("HTTP error")

    def json(self):
        return self._payload


class _FakeSession:
    """POST /orders → uuid, GET /order → 체결 내역을 순차 반환하는 스텁."""

    def __init__(self, order_detail: dict) -> None:
        self.order_detail = order_detail
        self.posted: list[dict] = []

    def post(self, url, params=None, headers=None, timeout=None):
        self.posted.append(params)
        return _FakeResp({"uuid": "ORDER-UUID"})

    def get(self, url, params=None, headers=None, timeout=None):
        return _FakeResp(self.order_detail)


def _exchange(order_detail: dict) -> tuple[UpbitExchange, _FakeSession]:
    session = _FakeSession(order_detail)
    ex = UpbitExchange("ak", "sk", session=session)  # type: ignore[arg-type]
    return ex, session


def test_buy_market_reflects_actual_fill_price():
    # 요청가 100,000,000 이지만 실제로는 100,500,000 에 체결 → 슬리피지 +50bp
    detail = {
        "state": "done",
        "executed_volume": "0.001",
        "paid_fee": "50.25",
        "trades": [
            {"funds": "60300.0", "volume": "0.0006"},
            {"funds": "40200.0", "volume": "0.0004"},
        ],
    }
    ex, _ = _exchange(detail)
    res = ex.buy_market("KRW-BTC", price=100_000_000, quantity=0.001)

    assert res.ok
    assert res.side is OrderSide.BUY
    # (60300+40200)/(0.0006+0.0004) = 100_500_000
    assert res.price == pytest.approx(100_500_000)
    assert res.quantity == pytest.approx(0.001)
    assert res.fee == pytest.approx(50.25)
    assert res.order_id == "ORDER-UUID"


def test_sell_market_weighted_average_fill():
    detail = {
        "state": "done",
        "executed_volume": "0.002",
        "paid_fee": "99.0",
        "trades": [
            {"funds": "99000.0", "volume": "0.001"},
            {"funds": "98000.0", "volume": "0.001"},
        ],
    }
    ex, _ = _exchange(detail)
    res = ex.sell_market("KRW-BTC", price=99_000_000, quantity=0.002)

    assert res.side is OrderSide.SELL
    assert res.price == pytest.approx(98_500_000)  # 197000 / 0.002
    assert res.quantity == pytest.approx(0.002)
    assert res.fee == pytest.approx(99.0)


def test_settle_falls_back_when_no_trades():
    # 체결 내역이 비어 있으면 요청가로 폴백 (과거 동작 보존)
    detail = {"state": "wait", "executed_volume": "0", "trades": []}
    ex, _ = _exchange(detail)
    res = ex.buy_market("KRW-BTC", price=100_000_000, quantity=0.001)

    assert res.ok
    assert res.price == pytest.approx(100_000_000)  # 폴백
    assert res.quantity == pytest.approx(0.001)


# --- MockExchange 슬리피지 모델 (paper/백테스트) -------------------------------
def test_mock_buy_slippage_adverse_up():
    # 10bp 슬리피지 → 매수 체결가 = 요청가 * 1.001
    ex = MockExchange(krw=1_000_000_000, btc=0.0, slippage_bp=10.0)
    res = ex.buy_market("KRW-BTC", price=100_000_000, quantity=0.001)

    assert res.ok
    assert res.price == pytest.approx(100_100_000)  # 위로 밀림
    assert res.quantity == pytest.approx(0.001)
    # 지불 KRW = 체결가*수량 + 수수료만큼 잔고 감소
    notional = 100_100_000 * 0.001
    assert ex.get_balance().krw == pytest.approx(
        1_000_000_000 - notional - notional * ex.fee_rate
    )


def test_mock_sell_slippage_adverse_down():
    ex = MockExchange(krw=0.0, btc=0.001, slippage_bp=10.0)
    res = ex.sell_market("KRW-BTC", price=100_000_000, quantity=0.001)

    assert res.ok
    assert res.price == pytest.approx(99_900_000)  # 아래로 밀림


def test_mock_zero_slippage_is_backward_compatible():
    # 기본값(0bp)은 과거 동작과 동일 — 요청가 그대로 체결
    ex = MockExchange(krw=1_000_000_000, btc=0.0)
    res = ex.buy_market("KRW-BTC", price=100_000_000, quantity=0.001)
    assert res.price == pytest.approx(100_000_000)


# --- 지정가 주문 + 시장가 폴백 (#3, UpbitExchange) ----------------------------
class _LimitSession:
    """POST(주문)→uuid, GET(조회), DELETE(취소) 스텁. 취소 후 다른 상세를 반환."""

    def __init__(self, uuids, live, cancelled=None) -> None:
        self._uuids = list(uuids)
        self.live = live               # uuid -> 취소 전 상세
        self.cancelled = cancelled or {}  # uuid -> 취소 후 상세
        self.posted: list[dict] = []
        self.deleted: list[str] = []

    def post(self, url, params=None, headers=None, timeout=None):
        self.posted.append(params)
        return _FakeResp({"uuid": self._uuids.pop(0)})

    def get(self, url, params=None, headers=None, timeout=None):
        u = params["uuid"]
        if u in self.deleted:
            return _FakeResp(self.cancelled.get(u, {"state": "cancel", "trades": []}))
        return _FakeResp(self.live[u])

    def delete(self, url, params=None, headers=None, timeout=None):
        self.deleted.append(params["uuid"])
        return _FakeResp({"uuid": params["uuid"], "state": "cancel"})


def _limit_exchange(session):
    return UpbitExchange(
        "ak", "sk", session=session,  # type: ignore[arg-type]
        order_type="limit", limit_wait_seconds=1.0, limit_offset_bp=0.0,
    )


def test_limit_fully_filled_no_fallback():
    # 지정가가 전량 체결되면 시장가 주문을 내지 않는다
    session = _LimitSession(
        uuids=["L1"],
        live={"L1": {"state": "done", "paid_fee": "46.7",
                     "trades": [{"funds": "93329.0", "volume": "0.001"}]}},
    )
    ex = _limit_exchange(session)
    res = ex.buy_market("KRW-BTC", price=93_329_000, quantity=0.001)

    assert res.ok
    assert res.price == pytest.approx(93_329_000)
    assert res.quantity == pytest.approx(0.001)
    assert len(session.posted) == 1     # 지정가 1건뿐, 시장가 폴백 없음
    assert session.deleted == []


def test_limit_unfilled_falls_back_to_market():
    # 지정가 미체결 → 취소 후 전량 시장가 체결(더 높은 가격)
    session = _LimitSession(
        uuids=["L1", "M1"],
        live={
            "L1": {"state": "wait", "trades": []},
            "M1": {"state": "done", "paid_fee": "47.0",
                   "trades": [{"funds": "93400.0", "volume": "0.001"}]},
        },
        cancelled={"L1": {"state": "cancel", "trades": []}},
    )
    ex = _limit_exchange(session)
    res = ex.buy_market("KRW-BTC", price=93_329_000, quantity=0.001)

    assert res.ok
    assert session.deleted == ["L1"]     # 지정가 취소됨
    assert len(session.posted) == 2      # 지정가 + 시장가 폴백
    assert res.price == pytest.approx(93_400_000)  # 시장가 체결가
    assert res.quantity == pytest.approx(0.001)


def test_limit_partial_fill_then_market_remainder():
    # 지정가로 0.0006 체결, 나머지 0.0004 는 시장가 → 가중평균가
    session = _LimitSession(
        uuids=["L1", "M1"],
        live={
            "L1": {"state": "wait", "trades": [{"funds": "55997.4", "volume": "0.0006"}]},
            "M1": {"state": "done", "paid_fee": "18.7",
                   "trades": [{"funds": "37360.0", "volume": "0.0004"}]},
        },
        cancelled={"L1": {"state": "cancel", "paid_fee": "28.0",
                          "trades": [{"funds": "55997.4", "volume": "0.0006"}]}},
    )
    ex = _limit_exchange(session)
    res = ex.buy_market("KRW-BTC", price=93_329_000, quantity=0.001)

    assert res.ok
    assert res.quantity == pytest.approx(0.001)
    # (55997.4 + 37360.0) / 0.001 = 93,357,400
    assert res.price == pytest.approx(93_357_400)
    assert res.fee == pytest.approx(28.0 + 18.7)


def test_sell_limit_price_rounds_up_to_tick():
    # 매도 지정가는 올림(≥요청가)으로 호가 단위 정렬
    from coinforge.exchange.base import OrderSide
    from coinforge.exchange.upbit import _round_to_tick

    assert _round_to_tick(93_329_500, OrderSide.BUY) == 93_329_000   # 내림
    assert _round_to_tick(93_329_500, OrderSide.SELL) == 93_330_000  # 올림
