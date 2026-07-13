"""MockNotifier — 전송 이벤트를 메모리에 수집 (CHECKLIST 8.6)."""

from __future__ import annotations

from .event import TradeEvent


class MockNotifier:
    def __init__(self) -> None:
        self.events: list[TradeEvent] = []

    def send(self, event: TradeEvent) -> bool:
        self.events.append(event)
        return True
