"""진입 로직 — 3관문 + 부가 조건 (CHECKLIST 5.1).

모든 관문 통과 시에만 매수 신호. 방어 로직(defense)은 별도로 평가하며,
오케스트레이터가 defense 통과 후 entry 를 평가한다.
"""

from __future__ import annotations

from dataclasses import dataclass

from .context import MarketState
from .pullback import detect_pullback


@dataclass
class EntryResult:
    signal: bool                 # 진입 신호 발생 여부
    reason: str                  # 사유 (통과/차단 관문)
    pullback_kind: str = ""      # "ma20" | "ma60" | ""
    volume_confirmed: bool = False  # 부가 조건 (신뢰도 가산)


def evaluate_entry(state: MarketState) -> EntryResult:
    """3관문을 순차 평가해 진입 신호를 반환한다.

    - 1관문 (장기 환경): 가격 > 구름 상단 AND bull 구름
    - 2관문 (추세 확인): MA200 < MA60 < MA20 정배열 AND 가격 > MA20
    - 3관문 (진입 트리거): 눌림목 반등 (D2)
    - 부가: 거래량 > 20봉 평균 → 신뢰도 플래그 (차단 아님)
    """
    ind = state.indicators

    # 1관문
    if not (ind.above_cloud and ind.is_bull_cloud):
        return EntryResult(False, "1관문 실패: 가격이 구름 상단 위 + 상승 구름 조건 미충족")

    # 2관문
    if not ind.ma_aligned_bull:
        return EntryResult(False, "2관문 실패: MA200<MA60<MA20 정배열 아님")
    if not (ind.close > ind.sma20):
        return EntryResult(False, "2관문 실패: 현재가가 MA20 아래")

    # 3관문 (D2 눌림목)
    pb = detect_pullback(state.frame)
    if not pb.triggered:
        return EntryResult(False, f"3관문 실패: {pb.reason}")

    volume_confirmed = ind.volume_above_avg
    vol_note = " · 거래량 확인(신뢰도↑)" if volume_confirmed else ""
    return EntryResult(
        signal=True,
        reason=f"진입 신호: 3관문 통과 — {pb.reason}{vol_note}",
        pullback_kind=pb.kind,
        volume_confirmed=volume_confirmed,
    )
