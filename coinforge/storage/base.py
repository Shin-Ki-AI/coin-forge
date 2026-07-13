"""Repository 인터페이스 (CHECKLIST 7.6).

포지션(현재 상태), 거래 로그, 일일 PnL(서킷 브레이커), 시스템 상태를 영속화한다.
"""

from __future__ import annotations

from datetime import date
from typing import Optional, Protocol, runtime_checkable

from ..domain.position import Position
from ..domain.trade import SignalLog, TradeLog


@runtime_checkable
class Repository(Protocol):
    # --- 포지션 (7.2) ---
    def get_open_position(self, market: str) -> Optional[Position]:
        ...

    def save_position(self, position: Position) -> None:
        ...

    def close_position(self, position_id: str) -> None:
        ...

    # --- 거래 로그 (7.3) ---
    def append_trade_log(self, log: TradeLog) -> None:
        ...

    def list_trade_logs(self, limit: int = 100) -> list[TradeLog]:
        ...

    def append_signal_log(self, log: SignalLog) -> None:
        ...

    # --- 일일 PnL (7.4, 서킷 브레이커) ---
    def add_realized_pnl(self, day: date, pnl_krw: float) -> None:
        ...

    def get_daily_loss(self, day: date) -> float:
        """당일 누적 손실액 (양수 = 손실). 이익뿐이면 0."""
        ...

    # --- 시스템 상태 (7.5) ---
    def get_state(self, key: str) -> Optional[str]:
        ...

    def set_state(self, key: str, value: str) -> None:
        ...
