"""IndicatorEngine — 240봉 캔들에서 지표 계산 (CHECKLIST 3.x).

계산 로직은 참조 구현 `scripts/coin-chart.py::compute_indicators()`와 수치가
일치하도록 이식했다. 특히 일목 구름은 senkou_a/b 를 26봉 선행(shift)한 뒤,
현재(마지막) 봉 위치의 구름 값을 사용한다.
"""

from __future__ import annotations

import pandas as pd

from .. import constants
from ..domain.candle import Candle, candles_to_dataframe
from ..domain.indicators import Indicators


class InsufficientCandlesError(ValueError):
    """지표 계산에 필요한 최소 봉 수 미달 (CHECKLIST 3.7)."""


def compute_indicator_frame(df: pd.DataFrame) -> pd.DataFrame:
    """OHLCV DataFrame → 지표 컬럼이 추가된 DataFrame.

    참조: coin-chart.py compute_indicators(). 컬럼명은 소문자 규약.
    """
    out = df.copy()
    close = out["close"]
    high = out["high"]
    low = out["low"]

    out["sma20"] = close.rolling(constants.MA_SHORT).mean()
    out["sma60"] = close.rolling(constants.MA_MID).mean()
    out["sma200"] = close.rolling(constants.MA_LONG).mean()

    tenkan = (
        high.rolling(constants.TENKAN_PERIOD).max()
        + low.rolling(constants.TENKAN_PERIOD).min()
    ) / 2
    kijun = (
        high.rolling(constants.KIJUN_PERIOD).max()
        + low.rolling(constants.KIJUN_PERIOD).min()
    ) / 2
    senkou_b_raw = (
        high.rolling(constants.SENKOU_B_PERIOD).max()
        + low.rolling(constants.SENKOU_B_PERIOD).min()
    ) / 2

    # 26봉 앞(미래)으로 이동 → 현재 봉 위치에서 참조하는 구름
    out["senkou_a"] = ((tenkan + kijun) / 2).shift(constants.ICHIMOKU_DISPLACEMENT)
    out["senkou_b"] = senkou_b_raw.shift(constants.ICHIMOKU_DISPLACEMENT)

    out["volume_avg20"] = out["volume"].rolling(constants.VOLUME_AVG_PERIOD).mean()

    return out


class IndicatorEngine:
    """단일 진입점 지표 계산기 (CHECKLIST 3.5)."""

    def __init__(self, min_candles: int = constants.CANDLE_COUNT) -> None:
        self.min_candles = min_candles

    def compute(self, candles: list[Candle]) -> Indicators:
        """캔들 목록에서 마지막 봉 기준 Indicators 스냅샷을 계산한다.

        Raises:
            InsufficientCandlesError: 봉 수가 min_candles 미만이거나
                마지막 봉의 지표가 NaN(계산 불가)인 경우.
        """
        if len(candles) < self.min_candles:
            raise InsufficientCandlesError(
                f"지표 계산에 최소 {self.min_candles}봉이 필요합니다: {len(candles)}봉 입력됨"
            )

        df = candles_to_dataframe(candles)
        frame = compute_indicator_frame(df)
        last = frame.iloc[-1]

        required = ["sma20", "sma60", "sma200", "senkou_a", "senkou_b"]
        missing = [c for c in required if pd.isna(last[c])]
        if missing:
            raise InsufficientCandlesError(
                f"마지막 봉의 지표를 계산할 수 없습니다 (NaN): {', '.join(missing)}. "
                f"봉 수가 부족하거나 데이터에 결측이 있습니다."
            )

        vol_avg = last["volume_avg20"]
        return Indicators(
            datetime=frame.index[-1].to_pydatetime(),
            close=float(last["close"]),
            sma20=float(last["sma20"]),
            sma60=float(last["sma60"]),
            sma200=float(last["sma200"]),
            senkou_a=float(last["senkou_a"]),
            senkou_b=float(last["senkou_b"]),
            volume=float(last["volume"]),
            volume_avg20=float(vol_avg) if not pd.isna(vol_avg) else 0.0,
        )
