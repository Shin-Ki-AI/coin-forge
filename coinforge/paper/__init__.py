"""모의투자(paper) — 지금부터 실시간으로 누적되는 지속 모의계좌 (#1).

백테스트(과거 일괄 평가)와 달리, 시작 자본에서 출발해 4시간마다 한 사이클씩
전진하며 자산곡선을 쌓는다. 실거래와 동일한 Orchestrator·전략·리스크를 재사용해
로직 드리프트를 방지한다.
"""

from .engine import PaperEngine, PaperState

__all__ = ["PaperEngine", "PaperState"]
