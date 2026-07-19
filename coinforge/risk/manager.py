"""RiskManager — 1% 룰 사이징, 손절가 산출, 서킷 브레이커 (CHECKLIST 6).

리스크 규칙만 평가하는 순수 로직. 일일 손실 누적치·포지션 보유 여부 등 상태는
호출자(오케스트레이터/스토리지)가 주입한다.
"""

from __future__ import annotations

from dataclasses import dataclass

from .. import constants
from ..config import Config
from ..domain.indicators import Indicators


@dataclass
class PositionSizing:
    quantity: float          # 매수 수량 (BTC)
    stop_price: float        # 손절가
    risk_per_unit: float     # 1R = entry - stop (KRW/BTC)
    risk_krw: float          # 이 거래의 최대 리스크 금액 (≈ equity * 1%)
    notional_krw: float      # 주문 금액 (quantity * entry)
    balance_limited: bool    # 잔고 부족으로 수량이 축소되었는가
    ok: bool                 # 주문 가능 여부
    reason: str = ""
    equity_capped: bool = False  # 비중 상한(max_position_pct)으로 수량이 제한되었는가


@dataclass
class TradingHalt:
    halted: bool
    reason: str


def compute_stop_price(entry_price: float, ind: Indicators) -> float:
    """손절가 = max(MA60, 구름 상단) — 두 손절 조건 중 먼저 닿는 상위 지지선.

    진입 시점엔 정배열(가격>MA20>MA60) & 구름 위이므로 두 값 모두 진입가 아래.
    둘 중 높은(가까운) 쪽이 실제로 먼저 트리거되는 구조적 손절선이다.
    """
    return max(ind.sma60, ind.cloud_top)


class RiskManager:
    """자금 관리·서킷 브레이커 판정기."""

    def __init__(self, config: Config, fee_buffer: float = constants.FEE_BUFFER_PCT) -> None:
        self.config = config
        self.fee_buffer = fee_buffer

    # --- 서킷 브레이커 (6.3, 6.4) ---------------------------------------------
    def check_trading_allowed(
        self, *, has_open_position: bool, daily_loss_krw: float, equity_krw: float
    ) -> TradingHalt:
        """신규 진입 허용 여부. daily_loss_krw 는 당일 실현 손실(양수=손실)."""
        limit = equity_krw * self.config.daily_loss_limit_pct
        # 경계값 포함: 정확히 3% 도달 시에도 중단 (>= )
        if daily_loss_krw >= limit:
            return TradingHalt(
                True,
                f"일일 손실 한도 도달 (당일 손실 {daily_loss_krw:,.0f} ≥ "
                f"{self.config.daily_loss_limit_pct:.0%} = {limit:,.0f}) — 당일 거래 중단",
            )
        if has_open_position:
            return TradingHalt(True, "이미 포지션 보유 중 (최대 1개) — 신규 진입 차단")
        return TradingHalt(False, "거래 허용")

    # --- 포지션 사이징 (6.1, 6.2, 6.5) ----------------------------------------
    def compute_sizing(
        self,
        *,
        entry_price: float,
        ind: Indicators,
        equity_krw: float,
        available_krw: float,
    ) -> PositionSizing:
        """포지션 사이징 (모드별). 세 단계로 수량을 정한다.

        1) 목표 주문금액 산출
           - risk  모드: 수량 = (equity * 1%) / (entry - stop) — 손절거리 기반
           - fixed 모드: 주문금액 = equity * fixed_position_pct — 고정 비율
        2) 비중 상한: 주문금액 > equity * max_position_pct 이면 상한으로 제한 (100% 올인 방지)
        3) 잔고 한도: 주문금액 > 가용 KRW 이면 잔고 내로 축소
        """
        stop_price = compute_stop_price(entry_price, ind)
        risk_per_unit = entry_price - stop_price

        if risk_per_unit <= 0:
            return PositionSizing(
                quantity=0.0,
                stop_price=stop_price,
                risk_per_unit=risk_per_unit,
                risk_krw=0.0,
                notional_krw=0.0,
                balance_limited=False,
                ok=False,
                reason="손절가가 진입가 이상 — 유효한 리스크 산출 불가",
            )

        # 1) 모드별 목표 주문금액
        if self.config.sizing_mode == constants.SIZING_MODE_FIXED:
            notional = equity_krw * self.config.fixed_position_pct
        else:  # risk (기본)
            notional = (equity_krw * self.config.risk_per_trade_pct) / risk_per_unit * entry_price

        # 2) 비중 상한 (100% 올인 방지)
        equity_capped = False
        max_notional = equity_krw * self.config.max_position_pct
        if notional > max_notional:
            equity_capped = True
            notional = max_notional

        # 3) 잔고 한도 (수수료·라운딩 여유 반영)
        balance_limited = False
        affordable = available_krw / (1.0 + self.fee_buffer)
        if notional > affordable:
            balance_limited = True
            notional = affordable

        quantity = notional / entry_price if entry_price > 0 else 0.0
        # 실제 이 거래가 감수하는 리스크 금액 (상한/잔고로 축소되면 1%보다 작아짐)
        risk_krw = quantity * risk_per_unit

        if quantity <= 0 or notional <= 0:
            return PositionSizing(
                quantity=0.0,
                stop_price=stop_price,
                risk_per_unit=risk_per_unit,
                risk_krw=0.0,
                notional_krw=0.0,
                balance_limited=balance_limited,
                ok=False,
                reason="가용 잔고 부족 — 주문 거부",
                equity_capped=equity_capped,
            )

        if balance_limited:
            reason = "잔고 한도로 수량 축소"
        elif equity_capped:
            reason = f"비중 상한(자본 {self.config.max_position_pct:.0%})으로 수량 제한"
        elif self.config.sizing_mode == constants.SIZING_MODE_FIXED:
            reason = f"고정 비율({self.config.fixed_position_pct:.0%}) 사이징 완료"
        else:
            reason = "1% 룰 사이징 완료"

        return PositionSizing(
            quantity=quantity,
            stop_price=stop_price,
            risk_per_unit=risk_per_unit,
            risk_krw=risk_krw,
            notional_krw=notional,
            balance_limited=balance_limited,
            ok=True,
            reason=reason,
            equity_capped=equity_capped,
        )
