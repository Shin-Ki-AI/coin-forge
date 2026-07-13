"""MockCandleProvider — 테스트·백테스트용 캔들 공급자 (CHECKLIST 4.3)."""

from __future__ import annotations

from ..domain.candle import Candle


class MockCandleProvider:
    """고정 캔들 목록을 반환. 백테스트에서 슬라이딩 윈도우로도 사용 가능."""

    def __init__(self, candles: list[Candle]) -> None:
        self._candles = sorted(candles, key=lambda c: c.datetime)

    def get_candles(self, count: int) -> list[Candle]:
        if len(self._candles) < count:
            raise RuntimeError(
                f"Mock 캔들 부족: {len(self._candles)}개 보유, {count}개 요청"
            )
        return self._candles[-count:]

    def set_candles(self, candles: list[Candle]) -> None:
        self._candles = sorted(candles, key=lambda c: c.datetime)
