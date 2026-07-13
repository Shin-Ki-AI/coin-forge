"""UpbitRestCandleProvider 완성봉 필터 테스트 (#4).

REST 최신 캔들은 형성 중(미완성)이므로, 타임스탬프 기준으로 아직 마감되지 않은
봉을 걸러 백테스트(완성봉)와 신호 기준을 일치시킨다.
"""

from __future__ import annotations

from datetime import datetime, timezone

from coinforge.bridge.upbit_rest import drop_forming
from coinforge.constants import TIMEFRAME_MINUTES

from .fixtures import make_candles


def _candles_from(start: datetime, n: int):
    """start 부터 4H 간격으로 n개 캔들 생성 (오름차순)."""
    cs = make_candles([100.0 + i for i in range(n)])
    # make_candles 는 자체 시각을 쓰므로 datetime 을 4H 그리드로 덮어씀
    from dataclasses import replace

    return [
        replace(c, datetime=start.replace(tzinfo=timezone.utc) + i * _four_h())
        for i, c in enumerate(cs)
    ]


def _four_h():
    from datetime import timedelta

    return timedelta(minutes=TIMEFRAME_MINUTES)


def test_drop_forming_removes_incomplete_last_candle():
    # 봉 시작시각: 00,04,08 (UTC). now=11:37 → [08,12) 는 미완성.
    start = datetime(2026, 7, 13, 0, 0)
    candles = _candles_from(start, 3)  # 00:00, 04:00, 08:00
    now = datetime(2026, 7, 13, 11, 37, tzinfo=timezone.utc)

    kept = drop_forming(candles, now)

    assert len(kept) == 2  # 08:00 봉(미완성) 제거
    assert kept[-1].datetime == datetime(2026, 7, 13, 4, 0, tzinfo=timezone.utc)


def test_drop_forming_keeps_all_when_boundary_passed():
    # now 가 마지막 봉의 마감(12:00) 이후면 전부 완성봉
    start = datetime(2026, 7, 13, 0, 0)
    candles = _candles_from(start, 3)  # ...08:00 봉은 12:00 마감
    now = datetime(2026, 7, 13, 12, 0, 1, tzinfo=timezone.utc)

    kept = drop_forming(candles, now)

    assert len(kept) == 3
    assert kept[-1].datetime == datetime(2026, 7, 13, 8, 0, tzinfo=timezone.utc)
