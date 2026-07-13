"""TelegramNotifier — 텔레그램 봇 알림 (CHECKLIST 8.2)."""

from __future__ import annotations

import logging

import requests

from .event import TradeEvent

log = logging.getLogger(__name__)


class TelegramNotifier:
    def __init__(self, bot_token: str, chat_id: str) -> None:
        self.bot_token = bot_token
        self.chat_id = chat_id
        self._url = f"https://api.telegram.org/bot{bot_token}/sendMessage"

    def send(self, event: TradeEvent) -> bool:
        if not self.bot_token or not self.chat_id:
            log.warning("텔레그램 설정 없음 — 전송 생략")
            return False
        try:
            resp = requests.post(
                self._url,
                json={"chat_id": self.chat_id, "text": event.format_message()},
                timeout=10,
            )
            resp.raise_for_status()
            return True
        except requests.RequestException as exc:
            log.error("텔레그램 전송 실패: %s", exc)
            return False
