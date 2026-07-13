"""신호 진단 테스트 (대시보드 /api/signal 로직)."""

from __future__ import annotations

import numpy as np

from coinforge.domain.position import Position
from coinforge.strategy import build_market_state, evaluate_signal

from .fixtures import linear_uptrend, make_candles


def _entry_candles():
    closes = linear_uptrend(240, start=50_000_000, step=30_000)
    lows = [c * 0.995 for c in closes]
    lows[-2] = float(np.mean(closes[-21:-1])) * 0.999
    return make_candles(closes, lows=lows)


def test_signal_entry_all_gates_pass():
    state = build_market_state(_entry_candles())
    diag = evaluate_signal(state, None)
    assert diag.decision == "entry"
    assert len(diag.gates) == 3
    assert all(g.passed for g in diag.gates)


def test_signal_blocked_on_downtrend():
    closes = list(reversed(linear_uptrend(240)))
    state = build_market_state(make_candles(closes))
    diag = evaluate_signal(state, None)
    assert diag.decision == "blocked"
    assert diag.defense_blocked


def test_signal_gates_always_three_and_serializable():
    closes = linear_uptrend(240, start=50_000_000, step=200_000)
    state = build_market_state(make_candles(closes, lows=closes, opens=closes, highs=closes))
    diag = evaluate_signal(state, None)
    d = diag.as_dict()
    assert len(d["gates"]) == 3
    assert set(d["gates"][0].keys()) == {"name", "passed", "detail"}
    assert d["decision"] in ("entry", "wait", "blocked")


def test_signal_exit_view_when_position_open():
    state = build_market_state(_entry_candles())
    price = state.indicators.close
    pos = Position(
        market="KRW-BTC", entry_price=price, quantity=1.0,
        stop_price=price * 0.95, initial_quantity=1.0,
    )
    diag = evaluate_signal(state, pos)
    # 포지션 보유 시 청산 관점(4개 청산 게이트) 반환
    assert diag.decision in ("hold", "exit", "full_exit", "partial_exit")
    assert len(diag.gates) == 4
