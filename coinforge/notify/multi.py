"""MultiNotifier — 여러 Notifier에 동시 전송 (텔레그램 + PushOver)."""

from __future__ import annotations

from .event import TradeEvent


class MultiNotifier:
    """등록된 모든 Notifier에 이벤트를 전달. 하나가 실패해도 나머지는 계속."""

    def __init__(self, notifiers: list) -> None:
        self._notifiers = notifiers

    def send(self, event: TradeEvent) -> bool:
        results = [n.send(event) for n in self._notifiers]
        return any(results) if results else False
