"""눌림목 반등 트리거 판정 (D2, CHECKLIST 5.1.3).

D2 제안 (CHECKLIST 채택):
1. MA20 눌림목: 직전 1~3봉 중 저가가 MA20 ±1% 이내 터치 후,
   현재봉 종가가 MA20 위로 재돌파.
2. MA60 깊은 눌림목: 직전 1~5봉 중 저가가 MA60 ±1.5% 이내 터치 후,
   현재봉 종가가 MA60 위로 재돌파.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from .. import constants


@dataclass
class PullbackResult:
    triggered: bool
    kind: str  # "ma20" | "ma60" | ""
    reason: str


def _touched_recently(
    frame: pd.DataFrame, ma_col: str, lookback: int, tol: float
) -> bool:
    """직전 lookback 봉(현재봉 제외) 중 저가가 MA ±tol 이내로 터치했는가."""
    if len(frame) < lookback + 1:
        return False
    # 마지막(현재) 봉 제외, 직전 lookback 봉
    window = frame.iloc[-(lookback + 1):-1]
    for _, row in window.iterrows():
        ma = row[ma_col]
        low = row["low"]
        if pd.isna(ma):
            continue
        if abs(low - ma) / ma <= tol:
            return True
    return False


def detect_pullback(frame: pd.DataFrame) -> PullbackResult:
    """지표 프레임에서 눌림목 반등 트리거를 판정한다.

    현재봉 = frame 의 마지막 행.
    """
    last = frame.iloc[-1]
    close = last["close"]

    # 1) MA20 눌림목
    ma20 = last["sma20"]
    if not pd.isna(ma20) and close > ma20:
        if _touched_recently(
            frame, "sma20", constants.MA20_PULLBACK_LOOKBACK, constants.MA20_PULLBACK_TOL
        ):
            return PullbackResult(
                triggered=True,
                kind="ma20",
                reason=(
                    f"MA20 눌림목 반등 (직전 {constants.MA20_PULLBACK_LOOKBACK}봉 내 "
                    f"±{constants.MA20_PULLBACK_TOL:.0%} 터치 후 종가 재돌파)"
                ),
            )

    # 2) MA60 깊은 눌림목
    ma60 = last["sma60"]
    if not pd.isna(ma60) and close > ma60:
        if _touched_recently(
            frame, "sma60", constants.MA60_PULLBACK_LOOKBACK, constants.MA60_PULLBACK_TOL
        ):
            return PullbackResult(
                triggered=True,
                kind="ma60",
                reason=(
                    f"MA60 깊은 눌림목 반등 (직전 {constants.MA60_PULLBACK_LOOKBACK}봉 내 "
                    f"±{constants.MA60_PULLBACK_TOL:.1%} 터치 후 종가 재돌파)"
                ),
            )

    return PullbackResult(triggered=False, kind="", reason="눌림목 반등 미발생")
