"""방어 로직 — 매수 차단 조건 (CHECKLIST 5.2).

단 하나라도 해당 시 즉시 매수 진입 차단.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from ..domain.indicators import Indicators
from ..domain.position import Position


@dataclass
class DefenseResult:
    blocked: bool
    reason: str


def evaluate_defense(
    ind: Indicators, position: Optional[Position] = None
) -> DefenseResult:
    """매수 차단 여부를 평가한다. blocked=True 면 진입 불가.

    차단 우선순위(위에서부터):
    1. 기존 포지션 보유 (중복 진입 방지)
    2. 시장 악화: 구름 아래 / 구름 내부 / bear 구름
    3. 추세 꺾임: MA200 > MA60 장기 역배열
    """
    if position is not None:
        return DefenseResult(True, "기존 포지션 보유 중 (중복 진입 차단)")

    if ind.below_cloud:
        return DefenseResult(True, "가격이 구름 아래 (하락장) — 매수 차단")

    if ind.inside_cloud:
        return DefenseResult(True, "가격이 구름 내부 (방향성 상실) — 매수 차단")

    if not ind.is_bull_cloud:
        return DefenseResult(True, "빨간색 하락 구름 (bear) — 매수 차단")

    if ind.ma_long_inverted:
        return DefenseResult(True, "MA200 > MA60 장기 역배열 진행 — 매수 차단")

    return DefenseResult(False, "방어 조건 없음")
