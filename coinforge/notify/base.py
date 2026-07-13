"""Notifier 인터페이스 (CHECKLIST 8.1)."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from .event import TradeEvent


@runtime_checkable
class Notifier(Protocol):
    def send(self, event: TradeEvent) -> bool:
        """이벤트 전송. 성공 여부 반환 (예외를 삼켜 루프를 막지 않는다)."""
        ...
