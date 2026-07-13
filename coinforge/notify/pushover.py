"""PushOverNotifier — PushOver 푸시 알림 (CHECKLIST 8.3)."""

from __future__ import annotations

import logging

import requests

from .event import TradeEvent

log = logging.getLogger(__name__)

_URL = "https://api.pushover.net/1/messages.json"


class PushOverNotifier:
    def __init__(self, user_key: str, api_token: str) -> None:
        self.user_key = user_key
        self.api_token = api_token

    def send(self, event: TradeEvent) -> bool:
        if not self.user_key or not self.api_token:
            log.warning("PushOver 설정 없음 — 전송 생략")
            return False
        try:
            resp = requests.post(
                _URL,
                data={
                    "token": self.api_token,
                    "user": self.user_key,
                    "title": f"Coin Forge · {event.type}",
                    "message": event.format_message(),
                },
                timeout=10,
            )
            resp.raise_for_status()
            return True
        except requests.RequestException as exc:
            log.error("PushOver 전송 실패: %s", exc)
            return False
