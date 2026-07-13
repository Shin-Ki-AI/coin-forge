"""FourHourScheduler — 4H 봉 마감 + 버퍼 후 사이클 실행 (CHECKLIST 9.1, D5).

봉 마감(00/04/08/12/16/20 UTC) 직후 buffer_seconds 만큼 대기해 WS 반영 지연을
흡수한 뒤 콜백을 호출한다. Graceful shutdown 지원(9.6).
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta, timezone
from typing import Callable

from .. import constants

log = logging.getLogger(__name__)


def next_boundary(now: datetime, period_minutes: int = constants.TIMEFRAME_MINUTES) -> datetime:
    """now 이후 가장 가까운 4H 경계 시각(UTC) 반환."""
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    minutes_since = (now - day_start).total_seconds() / 60
    n = int(minutes_since // period_minutes) + 1
    return day_start + timedelta(minutes=period_minutes * n)


class FourHourScheduler:
    def __init__(
        self,
        callback: Callable[[], None],
        buffer_seconds: int = constants.SCHEDULER_BUFFER_SECONDS,
        period_minutes: int = constants.TIMEFRAME_MINUTES,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.callback = callback
        self.buffer_seconds = buffer_seconds
        self.period_minutes = period_minutes
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._stop = threading.Event()

    def stop(self) -> None:
        """Graceful shutdown 신호 (9.6)."""
        self._stop.set()

    def run_forever(self) -> None:
        """봉 마감 + 버퍼마다 콜백 실행. stop() 호출 시 종료."""
        log.info("스케줄러 시작 (period=%dm, buffer=%ds)", self.period_minutes, self.buffer_seconds)
        while not self._stop.is_set():
            now = self._clock()
            target = next_boundary(now, self.period_minutes) + timedelta(seconds=self.buffer_seconds)
            wait = (target - now).total_seconds()
            if wait > 0 and self._stop.wait(timeout=wait):
                break
            if self._stop.is_set():
                break
            try:
                self.callback()
            except Exception:  # noqa: BLE001 — 루프는 죽지 않아야 함
                log.exception("사이클 실행 중 예외")
        log.info("스케줄러 종료")
