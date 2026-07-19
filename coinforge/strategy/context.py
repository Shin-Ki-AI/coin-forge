"""MarketState — 전략 평가에 필요한 지표 프레임 + 스냅샷 묶음.

진입 3관문(가격/MA/구름)은 마지막 봉 스냅샷으로 충분하지만, 눌림목(D2)은
직전 여러 봉의 저가·MA 값이 필요하므로 지표 프레임 전체를 함께 보관한다.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from ..domain.candle import Candle, candles_to_dataframe
from ..domain.indicators import Indicators
from ..indicators.engine import IndicatorEngine, compute_indicator_frame


@dataclass
class MarketState:
    """한 사이클 시점의 시장 상태."""

    frame: pd.DataFrame        # 지표 컬럼이 포함된 OHLCV 프레임 (오름차순)
    indicators: Indicators     # 마지막 봉 기준 스냅샷

    @property
    def price(self) -> float:
        return self.indicators.close


def build_market_state(
    candles: list[Candle], engine: IndicatorEngine | None = None, params=None
) -> MarketState:
    """캔들 목록에서 MarketState 를 만든다.

    engine.compute() 로 스냅샷 유효성(봉 수·NaN)을 검증한 뒤,
    눌림목 판정을 위한 전체 지표 프레임을 함께 반환한다.
    프레임과 스냅샷은 동일 params(engine.params)로 계산해 일관성을 유지한다.
    """
    engine = engine or IndicatorEngine(params=params)
    indicators = engine.compute(candles)  # 검증 포함 (InsufficientCandlesError)
    frame = compute_indicator_frame(candles_to_dataframe(candles), engine.params)
    return MarketState(frame=frame, indicators=indicators)
