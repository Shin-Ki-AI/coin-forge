"""청산 로직 — 익절·손절 (CHECKLIST 5.3).

동시 조건 시 '가장 보수적(손실 최소화)' 우선순위로 단 하나의 액션만 반환한다
(AGENTS.md §6 청산 우선순위):

1. 비상 하드스탑 −3%            → 전량 손절
2. MA60 이탈 / 구름 상단 이탈    → 전량 손절
3. 2R 도달                      → 50% 부분 익절 (아직 미실행 시)
4. 3R 도달 또는 MA20 하향 이탈   → 전량 익절
"""

from __future__ import annotations

from dataclasses import dataclass

from .. import constants
from ..domain.indicators import Indicators
from ..domain.position import ExitAction, Position


@dataclass
class ExitResult:
    action: ExitAction
    quantity: float   # 청산 수량 (0 이면 HOLD)
    reason: str
    pnl_pct: float    # 이 가격 기준 미실현 손익률


def evaluate_exit(position: Position, ind: Indicators) -> ExitResult:
    """포지션·지표 스냅샷으로 청산 액션을 평가한다.

    현재가는 지표 스냅샷의 종가(ind.close)를 사용한다.
    """
    price = ind.close
    pnl = position.unrealized_pnl_pct(price)
    r = position.r_multiple(price)

    def hold() -> ExitResult:
        return ExitResult(ExitAction.HOLD, 0.0, "청산 조건 미충족 (보유 유지)", pnl)

    # 1) 비상 하드스탑 -3%
    if pnl <= -constants.HARD_STOP_PCT:
        return ExitResult(
            ExitAction.FULL_EXIT,
            position.quantity,
            f"비상 하드스탑 발동 (손실률 {pnl:.2%} ≤ -{constants.HARD_STOP_PCT:.0%})",
            pnl,
        )

    # 2) 손절: MA60 이탈 → 구름 상단 이탈
    if price < ind.sma60:
        return ExitResult(
            ExitAction.FULL_EXIT,
            position.quantity,
            f"MA60 하향 이탈 손절 (가격 {price:,.0f} < MA60 {ind.sma60:,.0f})",
            pnl,
        )
    if price < ind.cloud_top:
        return ExitResult(
            ExitAction.FULL_EXIT,
            position.quantity,
            f"구름 상단 이탈 손절 (가격 {price:,.0f} < 구름상단 {ind.cloud_top:,.0f})",
            pnl,
        )

    # 3) 2R 부분 익절 (아직 실행 안 했을 때만)
    if not position.partial_taken and r >= constants.PARTIAL_TAKE_R:
        qty = position.initial_quantity * constants.PARTIAL_TAKE_RATIO
        qty = min(qty, position.quantity)
        return ExitResult(
            ExitAction.PARTIAL_EXIT,
            qty,
            f"2R 도달 부분 익절 50% (R={r:.2f}, 손익 {pnl:.2%})",
            pnl,
        )

    # 4) 전량 익절: 3R 도달 또는 MA20 하향 이탈
    if r >= constants.FULL_TAKE_R:
        return ExitResult(
            ExitAction.FULL_EXIT,
            position.quantity,
            f"3R 도달 전량 익절 (R={r:.2f}, 손익 {pnl:.2%})",
            pnl,
        )
    if price < ind.sma20:
        return ExitResult(
            ExitAction.FULL_EXIT,
            position.quantity,
            f"MA20 하향 이탈 전량 익절 (가격 {price:,.0f} < MA20 {ind.sma20:,.0f}, 손익 {pnl:.2%})",
            pnl,
        )

    return hold()
