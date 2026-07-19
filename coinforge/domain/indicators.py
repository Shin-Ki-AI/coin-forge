"""Indicators 타입 — 특정 봉 시점의 지표 스냅샷 (CHECKLIST 2.2).

INDEX.md 정의:
- SMA20/60/200 (종가 기준 단순이동평균)
- 구름 상단/하단 = max/min(senkou_a, senkou_b)
- 구름 색상: senkou_a > senkou_b → bull(녹색)
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class CloudColor(str, Enum):
    BULL = "bull"  # 녹색 상승 구름 (senkou_a > senkou_b)
    BEAR = "bear"  # 빨간색 하락 구름 (senkou_a <= senkou_b)


@dataclass(frozen=True, slots=True)
class Indicators:
    """마지막(현재) 봉 기준 지표 스냅샷."""

    datetime: datetime
    close: float

    sma20: float
    sma60: float
    sma200: float

    senkou_a: float
    senkou_b: float

    volume: float
    volume_avg20: float

    # 보조 기법 (기본 중립값 — 미계산 시에도 필터가 안전하게 통과)
    rsi: float = 50.0
    macd: float = 0.0
    macd_signal: float = 0.0

    @property
    def macd_bullish(self) -> bool:
        """MACD 라인이 시그널 위 (상승 모멘텀)."""
        return self.macd > self.macd_signal

    @property
    def cloud_top(self) -> float:
        return max(self.senkou_a, self.senkou_b)

    @property
    def cloud_bottom(self) -> float:
        return min(self.senkou_a, self.senkou_b)

    @property
    def cloud_color(self) -> CloudColor:
        return CloudColor.BULL if self.senkou_a > self.senkou_b else CloudColor.BEAR

    @property
    def is_bull_cloud(self) -> bool:
        return self.cloud_color == CloudColor.BULL

    @property
    def above_cloud(self) -> bool:
        """가격이 구름 상단 위에 있는가."""
        return self.close > self.cloud_top

    @property
    def below_cloud(self) -> bool:
        """가격이 구름 하단 아래에 있는가 (하락장)."""
        return self.close < self.cloud_bottom

    @property
    def inside_cloud(self) -> bool:
        """가격이 구름 내부에 갇혔는가 (방향성 상실)."""
        return self.cloud_bottom <= self.close <= self.cloud_top

    @property
    def ma_aligned_bull(self) -> bool:
        """정배열: MA200 < MA60 < MA20."""
        return self.sma200 < self.sma60 < self.sma20

    @property
    def ma_long_inverted(self) -> bool:
        """장기 역배열: MA200 > MA60."""
        return self.sma200 > self.sma60

    @property
    def volume_above_avg(self) -> bool:
        """현재 거래량 > 직전 20봉 평균 (신뢰도 가산)."""
        return self.volume > self.volume_avg20
