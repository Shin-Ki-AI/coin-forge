"""백테스트 데이터 로딩 — CSV 로드 및 1분봉 → 4H 리샘플 (CHECKLIST 10.1)."""

from __future__ import annotations

from datetime import timezone
from pathlib import Path

import pandas as pd

from .. import constants
from ..domain.candle import Candle


def load_csv(path: str | Path) -> pd.DataFrame:
    """OHLCV CSV 로드 (datetime, open, high, low, close, volume)."""
    df = pd.read_csv(path, comment="#", parse_dates=["datetime"])
    df = df.sort_values("datetime").set_index("datetime")
    return df[["open", "high", "low", "close", "volume"]]


def resample_to_4h(df: pd.DataFrame) -> pd.DataFrame:
    """1분봉(또는 임의 하위 봉) → 4H OHLCV 집계."""
    rule = f"{constants.TIMEFRAME_MINUTES}min"
    agg = df.resample(rule, label="left", closed="left").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
    )
    return agg.dropna(subset=["open", "high", "low", "close"])


def dataframe_to_candles(df: pd.DataFrame) -> list[Candle]:
    candles: list[Candle] = []
    for ts, row in df.iterrows():
        dt = ts.to_pydatetime()
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        candles.append(
            Candle(
                datetime=dt,
                open=float(row["open"]),
                high=float(row["high"]),
                low=float(row["low"]),
                close=float(row["close"]),
                volume=float(row["volume"]),
            )
        )
    return candles


def load_candles(path: str | Path, resample: bool = False) -> list[Candle]:
    """CSV → Candle 목록. resample=True 면 1분봉을 4H로 집계."""
    df = load_csv(path)
    if resample:
        df = resample_to_4h(df)
    return dataframe_to_candles(df)
