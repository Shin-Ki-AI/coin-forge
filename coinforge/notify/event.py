"""TradeEvent — 모든 Notifier 공통 이벤트 스키마 (AGENTS.md §10)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


@dataclass
class TradeEvent:
    type: str            # "entry" | "exit" | "partial_exit" | "error" | "circuit_breaker"
    market: str
    price: float = 0.0
    quantity: float = 0.0
    stop_price: Optional[float] = None
    target_2r: Optional[float] = None
    target_3r: Optional[float] = None
    pnl_percent: Optional[float] = None   # exit 시
    reason: str = ""                       # 한글 가능, 로그와 동일 문자열
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def format_message(self) -> str:
        """알림 본문 텍스트 생성 (진입가·규모·손절/목표·사유 포함, 8.5)."""
        icon = {
            "entry": "🟢 진입",
            "exit": "🔴 청산",
            "partial_exit": "🟡 부분 청산",
            "error": "⚠️ 오류",
            "circuit_breaker": "🛑 서킷 브레이커",
        }.get(self.type, self.type)

        lines = [f"[{icon}] {self.market}"]
        if self.price:
            lines.append(f"가격: {self.price:,.0f} KRW")
        if self.quantity:
            lines.append(f"수량: {self.quantity:.8f} BTC")
        if self.stop_price is not None:
            lines.append(f"손절가: {self.stop_price:,.0f}")
        if self.target_2r is not None:
            lines.append(f"2R 목표: {self.target_2r:,.0f}")
        if self.target_3r is not None:
            lines.append(f"3R 목표: {self.target_3r:,.0f}")
        if self.pnl_percent is not None:
            lines.append(f"손익률: {self.pnl_percent:+.2%}")
        if self.reason:
            lines.append(f"사유: {self.reason}")
        lines.append(f"시각: {self.timestamp.isoformat(timespec='seconds')}")
        return "\n".join(lines)
