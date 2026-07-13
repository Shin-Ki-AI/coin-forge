"""TradeLog / SignalLog 타입 — 거래·신호 이력 (CHECKLIST 2.4)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional


class TradeType(str, Enum):
    ENTRY = "entry"
    EXIT = "exit"
    PARTIAL_EXIT = "partial_exit"


@dataclass
class TradeLog:
    """체결된 거래 1건 (진입/청산/부분청산). 손익률·사유 기록."""

    trade_type: TradeType
    market: str
    price: float
    quantity: float
    reason: str
    position_id: str = ""
    stop_price: Optional[float] = None
    target_2r: Optional[float] = None
    target_3r: Optional[float] = None
    pnl_pct: Optional[float] = None       # 청산 시 실현 손익률
    pnl_krw: Optional[float] = None        # 청산 시 실현 손익액
    mode: str = "paper"                     # paper | live
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "trade_type": self.trade_type.value,
            "market": self.market,
            "price": self.price,
            "quantity": self.quantity,
            "reason": self.reason,
            "position_id": self.position_id,
            "stop_price": self.stop_price,
            "target_2r": self.target_2r,
            "target_3r": self.target_3r,
            "pnl_pct": self.pnl_pct,
            "pnl_krw": self.pnl_krw,
            "mode": self.mode,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class SignalLog:
    """매 사이클 평가 결과 기록 (진입/차단/청산 사유). 주문 없이도 남긴다."""

    market: str
    action: str          # "entry" | "blocked" | "exit" | "hold" | "no_signal"
    reason: str
    price: float
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    meta: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "market": self.market,
            "action": self.action,
            "reason": self.reason,
            "price": self.price,
            "timestamp": self.timestamp.isoformat(),
            "meta": self.meta,
        }
