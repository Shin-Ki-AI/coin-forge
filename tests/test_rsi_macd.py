"""RSI·MACD 보조 기법 테스트 (기법 추가).

지표 계산과, require_rsi/require_macd 진입 필터가 실제로 진입을 막는지 검증한다.
기본값(off)에서는 기존 동작과 동일함도 확인.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd

from coinforge.domain.candle import candles_to_dataframe
from coinforge.domain.indicators import Indicators
from coinforge.indicators.engine import compute_indicator_frame
from coinforge.strategy import MarketState, evaluate_entry
from coinforge.strategy.params import StrategyParams

from .fixtures import linear_uptrend, make_candles


def _ind(rsi=50.0, macd=1.0, macd_signal=0.0) -> Indicators:
    return Indicators(
        datetime=datetime(2026, 1, 1, tzinfo=timezone.utc),
        close=10_000_000.0, sma20=9_900_000.0, sma60=9_800_000.0, sma200=9_500_000.0,
        senkou_a=9_700_000.0, senkou_b=9_600_000.0, volume=100.0, volume_avg20=90.0,
        rsi=rsi, macd=macd, macd_signal=macd_signal,
    )


def _state(ind: Indicators) -> MarketState:
    return MarketState(frame=pd.DataFrame(), indicators=ind)


# 관문은 전부 끄고 보조 필터만 격리해 검증
_ONLY = dict(require_cloud=False, require_ma_alignment=False, require_pullback=False)


def test_rsi_computed_in_frame():
    candles = make_candles(linear_uptrend(60, start=50_000_000, step=40_000))
    frame = compute_indicator_frame(candles_to_dataframe(candles))
    assert "rsi" in frame and "macd" in frame and "macd_signal" in frame
    # 순수 상승 → 손실 0 → RSI 100 근처
    assert frame["rsi"].iloc[-1] > 99.0


def test_require_rsi_blocks_overbought():
    params = StrategyParams(require_rsi=True, rsi_overbought=70.0, **_ONLY)
    assert not evaluate_entry(_state(_ind(rsi=80.0)), params).signal   # 과매수 → 차단
    assert evaluate_entry(_state(_ind(rsi=55.0)), params).signal       # 정상 → 통과


def test_require_macd_blocks_bearish():
    params = StrategyParams(require_macd=True, **_ONLY)
    # MACD < 시그널 → 약세 → 차단
    assert not evaluate_entry(_state(_ind(macd=-1.0, macd_signal=0.5)), params).signal
    # MACD > 시그널 → 상승 → 통과
    assert evaluate_entry(_state(_ind(macd=1.0, macd_signal=0.5)), params).signal


def test_defaults_off_do_not_affect_entry():
    # 기본값(require_rsi/macd=False)에서는 과매수·약세여도 보조필터가 막지 않음
    params = StrategyParams(**_ONLY)  # 보조필터 기본 off
    assert evaluate_entry(_state(_ind(rsi=95.0, macd=-5.0, macd_signal=5.0)), params).signal


def test_presets_include_rsi_macd_and_run():
    from coinforge.backtest.compare import PRESETS, compare_configs
    from coinforge.config import Config

    candles = make_candles(linear_uptrend(400, start=50_000_000, step=40_000))
    cfg = Config(TRADING_MODE="paper", TOTAL_EQUITY_KRW=100_000_000)
    ranked = compare_configs(candles, cfg, PRESETS)
    names = {r["name"] for r in ranked}
    assert any("RSI" in n for n in names)
    assert any("MACD" in n for n in names)
    assert all("name" in r for r in ranked)


def test_config_strategy_params_reflects_env():
    # Config 로 켠 보조기법이 strategy_params() 에 반영됨 (실거래/모의투자 경로)
    from coinforge.config import Config

    cfg = Config(REQUIRE_RSI=True, REQUIRE_MACD=True, RSI_OVERBOUGHT=65)
    sp = cfg.strategy_params()
    assert sp.require_rsi and sp.require_macd
    assert sp.rsi_overbought == 65
