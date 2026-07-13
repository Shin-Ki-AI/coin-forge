"""지표 엔진 단위 테스트 (CHECKLIST 3.6, 3.7).

참조 구현 scripts/coin-chart.py 의 rolling 공식을 독립적으로 재현해 교차 검증한다.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from coinforge import constants
from coinforge.domain.candle import candles_to_dataframe
from coinforge.domain.indicators import CloudColor
from coinforge.indicators.engine import IndicatorEngine, InsufficientCandlesError

from .fixtures import linear_uptrend, make_candles


def _reference_frame(df: pd.DataFrame) -> pd.DataFrame:
    """coin-chart.py compute_indicators 와 동일한 공식 (독립 재현)."""
    close, high, low = df["close"], df["high"], df["low"]
    out = df.copy()
    out["sma20"] = close.rolling(20).mean()
    out["sma60"] = close.rolling(60).mean()
    out["sma200"] = close.rolling(200).mean()
    tenkan = (high.rolling(9).max() + low.rolling(9).min()) / 2
    kijun = (high.rolling(26).max() + low.rolling(26).min()) / 2
    senkou_b_raw = (high.rolling(52).max() + low.rolling(52).min()) / 2
    out["senkou_a"] = ((tenkan + kijun) / 2).shift(26)
    out["senkou_b"] = senkou_b_raw.shift(26)
    return out


def test_sma_matches_direct_mean():
    closes = linear_uptrend(240)
    candles = make_candles(closes)
    ind = IndicatorEngine().compute(candles)
    # 마지막 봉 SMA20 = 마지막 20개 종가 평균
    assert ind.sma20 == pytest.approx(np.mean(closes[-20:]))
    assert ind.sma60 == pytest.approx(np.mean(closes[-60:]))
    assert ind.sma200 == pytest.approx(np.mean(closes[-200:]))


def test_ichimoku_matches_reference():
    closes = linear_uptrend(240)
    candles = make_candles(closes)
    df = candles_to_dataframe(candles)
    ref = _reference_frame(df)
    ind = IndicatorEngine().compute(candles)
    assert ind.senkou_a == pytest.approx(ref["senkou_a"].iloc[-1])
    assert ind.senkou_b == pytest.approx(ref["senkou_b"].iloc[-1])


def test_uptrend_is_bull_cloud_and_aligned():
    ind = IndicatorEngine().compute(make_candles(linear_uptrend(240)))
    assert ind.cloud_color == CloudColor.BULL
    assert ind.is_bull_cloud
    assert ind.ma_aligned_bull          # MA200 < MA60 < MA20
    assert ind.above_cloud              # 가격 > 구름 상단
    assert not ind.ma_long_inverted


def test_downtrend_is_bear_cloud():
    closes = list(reversed(linear_uptrend(240)))  # 하락 추세
    ind = IndicatorEngine().compute(make_candles(closes))
    assert ind.cloud_color == CloudColor.BEAR
    assert not ind.ma_aligned_bull
    assert ind.ma_long_inverted         # MA200 > MA60


def test_insufficient_candles_raises():
    candles = make_candles(linear_uptrend(239))
    with pytest.raises(InsufficientCandlesError):
        IndicatorEngine().compute(candles)


def test_cloud_top_bottom():
    ind = IndicatorEngine().compute(make_candles(linear_uptrend(240)))
    assert ind.cloud_top == max(ind.senkou_a, ind.senkou_b)
    assert ind.cloud_bottom == min(ind.senkou_a, ind.senkou_b)


def test_volume_avg_period():
    closes = linear_uptrend(240)
    vols = [100.0] * 239 + [500.0]
    ind = IndicatorEngine().compute(make_candles(closes, volumes=vols))
    # 마지막 봉 제외 20봉 평균 대비 현재 거래량 비교
    assert ind.volume == 500.0
    assert ind.volume_above_avg
    assert ind.volume_avg20 == pytest.approx(np.mean(vols[-constants.VOLUME_AVG_PERIOD:]))
