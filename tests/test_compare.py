"""전략 설정 비교 테스트 (#2).

여러 StrategyParams 를 같은 캔들로 백테스트해 순위 매기는지, 파라미터가 실제로
백테스트 동작을 바꾸는지 검증한다.
"""

from __future__ import annotations

from coinforge.backtest.compare import compare_configs
from coinforge.backtest.engine import BacktestEngine
from coinforge.config import Config
from coinforge.strategy.params import StrategyParams

from .fixtures import linear_uptrend, make_candles


def _cfg():
    return Config(TRADING_MODE="paper", TOTAL_EQUITY_KRW=100_000_000)


def test_compare_ranks_configs():
    candles = make_candles(linear_uptrend(400, start=50_000_000, step=40_000))
    named = {
        "기본": StrategyParams(),
        "눌림목 없이": StrategyParams(require_pullback=False),
        "빠른 MA": StrategyParams(ma_short=10, ma_mid=30, ma_long=120),
    }
    ranked = compare_configs(candles, _cfg(), named)

    assert len(ranked) == 3
    # 성공한 설정은 rank 가 1..n 로 매겨짐
    ok = [r for r in ranked if r["ok"]]
    assert ok[0]["rank"] == 1
    for r in ok:
        assert "metrics" in r and "params" in r
    # 순위는 (게이트통과, 손익비, 승률) 내림차순
    assert ok == sorted(ok, key=lambda r: r["rank"])


def test_params_change_backtest_behavior():
    # 청산 배수를 좁히면 더 일찍 익절 → 최종 자산이 달라져야 함(파라미터 실제 반영)
    candles = make_candles(linear_uptrend(400, start=50_000_000, step=40_000))
    cfg = _cfg()
    wide = BacktestEngine(candles, cfg, params=StrategyParams()).run()  # 2R/3R
    tight = BacktestEngine(
        candles, cfg, params=StrategyParams(partial_take_r=1.0, full_take_r=1.5)
    ).run()
    assert tight.metrics.final_equity != wide.metrics.final_equity


def test_default_params_match_no_params():
    # StrategyParams() 기본값 = params 미지정과 동일 결과 (하위 호환)
    candles = make_candles(linear_uptrend(400, start=50_000_000, step=40_000))
    cfg = _cfg()
    a = BacktestEngine(candles, cfg).run()
    b = BacktestEngine(candles, cfg, params=StrategyParams()).run()
    assert a.metrics.total_trades == b.metrics.total_trades
    assert a.metrics.return_pct == b.metrics.return_pct
