"""StrategyParams — 전략 튜닝 파라미터 (#2).

이평선 기간·청산 배수·각 관문 on/off 를 한 곳에 모아 백테스트로 여러 설정을
비교할 수 있게 한다. 기본값은 기존 constants 와 동일하므로 params 를 넘기지 않으면
현재 전략과 정확히 같게 동작한다(하위 호환).
"""

from __future__ import annotations

from dataclasses import dataclass

from .. import constants


@dataclass(frozen=True)
class StrategyParams:
    # 이평선 기간 (단기/중기/장기)
    ma_short: int = constants.MA_SHORT
    ma_mid: int = constants.MA_MID
    ma_long: int = constants.MA_LONG

    # 청산 R 배수·하드스탑
    partial_take_r: float = constants.PARTIAL_TAKE_R
    full_take_r: float = constants.FULL_TAKE_R
    hard_stop_pct: float = constants.HARD_STOP_PCT

    # 진입 관문 on/off
    require_cloud: bool = True          # 1관문: 구름 위 + bull 구름
    require_ma_alignment: bool = True   # 2관문: MA 정배열 + 가격>MA20
    require_pullback: bool = True       # 3관문: 눌림목 반등
    require_volume: bool = False        # 거래량 > 평균을 '차단 조건'으로 승격

    # 보조 기법 (기본 off — 켜면 추가 진입 필터)
    require_rsi: bool = False           # RSI 과매수면 진입 보류
    rsi_period: int = constants.RSI_PERIOD
    rsi_overbought: float = constants.RSI_OVERBOUGHT
    require_macd: bool = False          # MACD < 시그널(약세)이면 진입 보류
    macd_fast: int = constants.MACD_FAST
    macd_slow: int = constants.MACD_SLOW
    macd_signal_period: int = constants.MACD_SIGNAL


DEFAULT_PARAMS = StrategyParams()
