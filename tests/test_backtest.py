"""백테스트 엔진·지표·게이트 테스트 (CHECKLIST 10)."""

from __future__ import annotations

from datetime import datetime, timezone

from coinforge.backtest.data import resample_to_4h
from coinforge.backtest.engine import BacktestEngine
from coinforge.backtest.metrics import (
    MIN_PROFIT_FACTOR,
    MIN_WIN_RATE,
    compute_metrics,
    passes_gate,
)
from coinforge.config import Config
from coinforge.domain.trade import TradeLog, TradeType

from .fixtures import linear_uptrend, make_candles

import pandas as pd


def _exit_log(pid: str, pnl: float) -> TradeLog:
    return TradeLog(
        trade_type=TradeType.EXIT, market="KRW-BTC", price=1.0, quantity=1.0,
        reason="t", position_id=pid, pnl_krw=pnl,
    )


def test_metrics_win_rate_and_profit_factor():
    logs = [_exit_log("a", 300), _exit_log("b", 200), _exit_log("c", -100), _exit_log("d", -100)]
    m = compute_metrics(logs, equity_curve=[1000, 1300], initial_equity=1000)
    assert m.total_trades == 4
    assert m.wins == 2 and m.losses == 2
    assert m.win_rate == 0.5
    # gross_profit=500, gross_loss=200 → PF=2.5
    assert round(m.profit_factor, 2) == 2.5


def test_gate_pass_and_fail():
    good = compute_metrics(
        [_exit_log("a", 300), _exit_log("b", 300), _exit_log("c", -100)],
        [1000, 1500], 1000,
    )
    ok, _ = passes_gate(good)
    assert ok  # 승률 66% ≥45%, PF=6 ≥1.5

    bad = compute_metrics([_exit_log("a", 100), _exit_log("b", -300)], [1000, 800], 1000)
    ok2, reason = passes_gate(bad)
    assert not ok2
    assert "배포 차단" in reason


def test_gate_thresholds_constants():
    assert MIN_WIN_RATE == 0.45
    assert MIN_PROFIT_FACTOR == 1.5


def test_resample_1m_to_4h():
    idx = pd.date_range("2026-01-01", periods=480, freq="1min", tz="UTC")
    df = pd.DataFrame(
        {"open": range(480), "high": range(480), "low": range(480),
         "close": range(480), "volume": [1] * 480},
        index=idx,
    )
    out = resample_to_4h(df)
    # 480분 = 2 x 4H 봉
    assert len(out) == 2
    assert out.iloc[0]["open"] == 0
    assert out.iloc[0]["volume"] == 240


def test_backtest_runs_end_to_end():
    # 상승 추세 300봉 → 최소 한 사이클 이상 실행되고 리포트 생성
    candles = make_candles(linear_uptrend(300, start=50_000_000, step=40_000))
    config = Config(TRADING_MODE="paper", TOTAL_EQUITY_KRW=100_000_000)
    report = BacktestEngine(candles, config).run()
    assert report.metrics is not None
    assert len(report.equity_curve) > 0
    # 게이트 판정 문자열 존재
    assert isinstance(report.gate_passed, bool)
