"""Candle 타입 — 4H OHLCV 봉 (CHECKLIST 2.1)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable

import pandas as pd


@dataclass(frozen=True, slots=True)
class Candle:
    """단일 4시간 OHLCV 봉. 시각은 봉 시작 시각(UTC)."""

    datetime: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "datetime": self.datetime.isoformat(),
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "volume": self.volume,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Candle":
        return cls(
            datetime=_parse_dt(d["datetime"]),
            open=float(d["open"]),
            high=float(d["high"]),
            low=float(d["low"]),
            close=float(d["close"]),
            volume=float(d["volume"]),
        )


def _parse_dt(value: Any) -> datetime:
    if isinstance(value, datetime):
        dt = value
    else:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def candles_from_dicts(rows: Iterable[dict[str, Any]]) -> list[Candle]:
    """dict 목록 → Candle 목록 (시각 오름차순 정렬)."""
    candles = [Candle.from_dict(r) for r in rows]
    candles.sort(key=lambda c: c.datetime)
    return candles


def candles_to_dataframe(candles: list[Candle]) -> pd.DataFrame:
    """Candle 목록 → 지표 계산용 DataFrame (datetime 인덱스, 오름차순).

    컬럼: open, high, low, close, volume (소문자, 지표 엔진 규약).
    """
    if not candles:
        return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])
    ordered = sorted(candles, key=lambda c: c.datetime)
    df = pd.DataFrame(
        {
            "datetime": [c.datetime for c in ordered],
            "open": [c.open for c in ordered],
            "high": [c.high for c in ordered],
            "low": [c.low for c in ordered],
            "close": [c.close for c in ordered],
            "volume": [c.volume for c in ordered],
        }
    )
    df = df.set_index("datetime")
    return df
