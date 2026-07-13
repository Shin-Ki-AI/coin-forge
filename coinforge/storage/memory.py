"""InMemoryRepository — paper/테스트/백테스트용 인메모리 저장소."""

from __future__ import annotations

from datetime import date
from typing import Optional

from ..domain.position import Position
from ..domain.trade import SignalLog, TradeLog


class InMemoryRepository:
    def __init__(self) -> None:
        self._positions: dict[str, Position] = {}   # market -> open position
        self._trade_logs: list[TradeLog] = []
        self._signal_logs: list[SignalLog] = []
        self._daily_pnl: dict[date, float] = {}
        self._state: dict[str, str] = {}

    def get_open_position(self, market: str) -> Optional[Position]:
        return self._positions.get(market)

    def save_position(self, position: Position) -> None:
        self._positions[position.market] = position

    def close_position(self, position_id: str) -> None:
        for market, pos in list(self._positions.items()):
            if pos.position_id == position_id:
                del self._positions[market]

    def append_trade_log(self, log: TradeLog) -> None:
        self._trade_logs.append(log)

    def list_trade_logs(self, limit: int = 100) -> list[TradeLog]:
        return self._trade_logs[-limit:]

    def append_signal_log(self, log: SignalLog) -> None:
        self._signal_logs.append(log)

    def add_realized_pnl(self, day: date, pnl_krw: float) -> None:
        self._daily_pnl[day] = self._daily_pnl.get(day, 0.0) + pnl_krw

    def get_daily_loss(self, day: date) -> float:
        net = self._daily_pnl.get(day, 0.0)
        return -net if net < 0 else 0.0

    def get_state(self, key: str) -> Optional[str]:
        return self._state.get(key)

    def set_state(self, key: str, value: str) -> None:
        self._state[key] = value
