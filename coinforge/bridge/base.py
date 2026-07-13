"""CandleProvider 인터페이스 (CHECKLIST 4.3).

캔들 수집 소스(UpbitBridge WS, Upbit REST, Mock)를 추상화한다.
전략/엔진/백테스트는 이 인터페이스에만 의존한다.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from ..domain.candle import Candle


@runtime_checkable
class CandleProvider(Protocol):
    """4H 캔들 공급자."""

    def get_candles(self, count: int) -> list[Candle]:
        """최근 count 개의 4H 캔들을 시각 오름차순으로 반환한다.

        Raises:
            RuntimeError: 요청 개수만큼 확보하지 못한 경우.
        """
        ...
