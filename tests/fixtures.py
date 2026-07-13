"""테스트용 캔들 생성 헬퍼 (결정론적)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from coinforge.constants import TIMEFRAME_MINUTES
from coinforge.domain.candle import Candle

BASE = datetime(2026, 1, 1, tzinfo=timezone.utc)


def make_candles(
    closes: list[float],
    *,
    highs: list[float] | None = None,
    lows: list[float] | None = None,
    volumes: list[float] | None = None,
    opens: list[float] | None = None,
) -> list[Candle]:
    """종가 목록으로 4H 캔들 목록을 만든다. 미지정 시 close 기반 기본값."""
    n = len(closes)
    highs = highs or [c * 1.005 for c in closes]
    lows = lows or [c * 0.995 for c in closes]
    volumes = volumes or [100.0] * n
    opens = opens or ([closes[0]] + closes[:-1])
    candles = []
    for i in range(n):
        candles.append(
            Candle(
                datetime=BASE + timedelta(minutes=TIMEFRAME_MINUTES * i),
                open=opens[i],
                high=max(highs[i], opens[i], closes[i]),
                low=min(lows[i], opens[i], closes[i]),
                close=closes[i],
                volume=volumes[i],
            )
        )
    return candles


def linear_uptrend(n: int = 240, start: float = 50_000_000.0, step: float = 50_000.0) -> list[float]:
    """완만한 상승 추세 종가 (정배열·상승 구름 유도)."""
    return [start + step * i for i in range(n)]
