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


def evaluate_entry(state: MarketState, params=None) -> EntryResult:
    """관문을 순차 평가해 진입 신호를 반환한다.

    - 1관문 (장기 환경): 가격 > 구름 상단 AND bull 구름       [require_cloud]
    - 2관문 (추세 확인): MA200 < MA60 < MA20 정배열 AND 가격>MA20 [require_ma_alignment]
    - 3관문 (진입 트리거): 눌림목 반등 (D2)                    [require_pullback]
    - 거래량: 기본은 신뢰도 플래그. require_volume=True 면 차단 조건.

    params(StrategyParams) 로 각 관문을 켜고 끌 수 있다. None 이면 전부 활성(현재 동작).
    """
    from .params import DEFAULT_PARAMS

    p = params or DEFAULT_PARAMS
    ind = state.indicators

    # 1관문
    if p.require_cloud and not (ind.above_cloud and ind.is_bull_cloud):
        return EntryResult(False, "1관문 실패: 가격이 구름 상단 위 + 상승 구름 조건 미충족")

    # 2관문
    if p.require_ma_alignment:
        if not ind.ma_aligned_bull:
            return EntryResult(False, "2관문 실패: MA200<MA60<MA20 정배열 아님")
        if not (ind.close > ind.sma20):
            return EntryResult(False, "2관문 실패: 현재가가 MA20 아래")

    # 3관문 (D2 눌림목)
    pullback_kind = ""
    pb_note = ""
    if p.require_pullback:
        pb = detect_pullback(state.frame)
        if not pb.triggered:
            return EntryResult(False, f"3관문 실패: {pb.reason}")
        pullback_kind = pb.kind
        pb_note = f" — {pb.reason}"

    volume_confirmed = ind.volume_above_avg
    if p.require_volume and not volume_confirmed:
        return EntryResult(False, "거래량 조건 실패: 현재 거래량이 20봉 평균 이하")

    vol_note = " · 거래량 확인(신뢰도↑)" if volume_confirmed else ""
    return EntryResult(
        signal=True,
        reason=f"진입 신호: 관문 통과{pb_note}{vol_note}",
        pullback_kind=pullback_kind,
        volume_confirmed=volume_confirmed,
    )
