"""Position 타입 — 보유 포지션 상태 (CHECKLIST 2.3).

청산 로직에 필요한 필드: 진입가, 수량, 손절가, 1R, 부분청산 여부, 목표가.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from .. import constants


class PositionSide(str, Enum):
    LONG = "long"  # 본 시스템은 롱 전용


class ExitAction(str, Enum):
    HOLD = "hold"
    PARTIAL_EXIT = "partial_exit"  # 2R 부분 익절
    FULL_EXIT = "full_exit"        # 전량 청산 (익절/손절)


@dataclass
class Position:
    """보유 포지션. 롱 기준 R-Multiple 계산."""

    market: str
    entry_price: float
    quantity: float          # 현재 잔여 수량 (부분청산 반영)
    stop_price: float        # 손절가 (진입 시 확정)
    entry_reason: str = ""
    opened_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    partial_taken: bool = False  # 2R 부분 익절 실행 여부
    initial_quantity: float = 0.0  # 진입 시점 총 수량
    position_id: str = field(default_factory=lambda: uuid4().hex)

    def __post_init__(self) -> None:
        if self.initial_quantity <= 0:
            self.initial_quantity = self.quantity

    @property
    def side(self) -> PositionSide:
        return PositionSide.LONG

    @property
    def risk_per_unit(self) -> float:
        """1R = 진입가 - 손절가 (롱). 항상 양수여야 유효한 포지션."""
        return self.entry_price - self.stop_price

    @property
    def target_2r(self) -> float:
        return self.entry_price + constants.PARTIAL_TAKE_R * self.risk_per_unit

    @property
    def target_3r(self) -> float:
        return self.entry_price + constants.FULL_TAKE_R * self.risk_per_unit

    @property
    def hard_stop_price(self) -> float:
        """비상 하드스탑 가격 (-3%)."""
        return self.entry_price * (1.0 - constants.HARD_STOP_PCT)

    def unrealized_pnl_pct(self, price: float) -> float:
        """현재가 기준 미실현 손익률."""
        return (price - self.entry_price) / self.entry_price

    def r_multiple(self, price: float) -> float:
        """현재가가 몇 R에 도달했는지."""
        if self.risk_per_unit <= 0:
            return 0.0
        return (price - self.entry_price) / self.risk_per_unit

    def to_dict(self) -> dict[str, Any]:
        return {
            "position_id": self.position_id,
            "market": self.market,
            "entry_price": self.entry_price,
            "quantity": self.quantity,
            "initial_quantity": self.initial_quantity,
            "stop_price": self.stop_price,
            "entry_reason": self.entry_reason,
            "opened_at": self.opened_at.isoformat(),
            "partial_taken": self.partial_taken,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Position":
        opened = d.get("opened_at")
        if isinstance(opened, str):
            opened_at = datetime.fromisoformat(opened)
        elif isinstance(opened, datetime):
            opened_at = opened
        else:
            opened_at = datetime.now(timezone.utc)
        return cls(
            market=d["market"],
            entry_price=float(d["entry_price"]),
            quantity=float(d["quantity"]),
            stop_price=float(d["stop_price"]),
            entry_reason=d.get("entry_reason", ""),
            opened_at=opened_at,
            partial_taken=bool(d.get("partial_taken", False)),
            initial_quantity=float(d.get("initial_quantity", d["quantity"])),
            position_id=d.get("position_id", uuid4().hex),
        )
