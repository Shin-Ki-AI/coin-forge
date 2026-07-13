"""전략 엔진 단위 테스트 (CHECKLIST 5.x)."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from coinforge.domain.indicators import Indicators
from coinforge.domain.position import ExitAction, Position
from coinforge.strategy import (
    build_market_state,
    evaluate_defense,
    evaluate_entry,
    evaluate_exit,
)

from .fixtures import linear_uptrend, make_candles


def _ind(**kw) -> Indicators:
    """기본값 위에 필드를 덮어써 Indicators 스냅샷 생성."""
    base = dict(
        datetime=datetime(2026, 1, 1, tzinfo=timezone.utc),
        close=105.0,
        sma20=100.0,
        sma60=95.0,
        sma200=90.0,
        senkou_a=98.0,
        senkou_b=96.0,   # bull cloud, top=98
        volume=120.0,
        volume_avg20=100.0,
    )
    base.update(kw)
    return Indicators(**base)


# --- 방어 로직 (5.2) ----------------------------------------------------------

def test_defense_blocks_when_position_held():
    pos = Position(market="KRW-BTC", entry_price=100, quantity=1, stop_price=95)
    assert evaluate_defense(_ind(), position=pos).blocked


def test_defense_blocks_below_cloud():
    ind = _ind(close=90.0)  # 구름 하단(96) 아래
    assert evaluate_defense(ind).blocked


def test_defense_blocks_inside_cloud():
    ind = _ind(close=97.0)  # 96~98 구름 내부
    assert evaluate_defense(ind).blocked


def test_defense_blocks_bear_cloud():
    ind = _ind(senkou_a=96.0, senkou_b=98.0, close=105.0)  # bear
    assert evaluate_defense(ind).blocked


def test_defense_blocks_ma_long_inverted():
    ind = _ind(sma200=96.0, sma60=95.0)  # MA200 > MA60
    assert evaluate_defense(ind).blocked


def test_defense_passes_clean():
    assert not evaluate_defense(_ind()).blocked


# --- 진입 로직 (5.1) — 프레임 기반 눌림목 포함 --------------------------------

def _uptrend_with_ma20_pullback():
    """정배열 상승 추세 + 마지막 직전 봉이 MA20 근처로 눌림, 현재봉 재돌파."""
    closes = linear_uptrend(240, start=50_000_000, step=30_000)
    lows = [c * 0.995 for c in closes]
    # 직전 봉(-2)의 저가를 그 시점 MA20 근처(≈ 마지막 20봉 평균)로 끌어내림
    return closes, lows


def test_entry_full_pass_generates_signal():
    closes, lows = _uptrend_with_ma20_pullback()
    # 직전 2번째 봉 저가를 MA20 부근까지 내림 (터치 유도)
    import numpy as np

    ma20_at_prev = float(np.mean(closes[-21:-1]))
    lows[-2] = ma20_at_prev * 0.999  # ±1% 이내
    candles = make_candles(closes, lows=lows)
    state = build_market_state(candles)
    res = evaluate_entry(state)
    assert res.signal, res.reason
    assert res.pullback_kind == "ma20"


def test_entry_fails_gate1_below_cloud():
    # 하락 추세 → 구름 위 아님
    closes = list(reversed(linear_uptrend(240)))
    state = build_market_state(make_candles(closes))
    assert not evaluate_entry(state).signal


def test_entry_fails_without_pullback():
    # 정배열이지만 눌림목 터치가 없음: 저가를 종가와 같게 두어 MA20 근처로 내려오지 않음
    closes = linear_uptrend(240, start=50_000_000, step=200_000)
    # 저가·시가·고가를 모두 종가로 → 저가가 MA20(종가보다 ~2% 아래)에 닿지 않음
    state = build_market_state(
        make_candles(closes, lows=closes, opens=closes, highs=closes)
    )
    res = evaluate_entry(state)
    # 1·2관문은 통과할 수 있으나 3관문(눌림목) 실패
    assert not res.signal
    assert "3관문" in res.reason


# --- 청산 로직 (5.3) ----------------------------------------------------------

def _pos() -> Position:
    return Position(
        market="KRW-BTC", entry_price=100.0, quantity=2.0, stop_price=90.0,
        initial_quantity=2.0,
    )


def test_exit_hard_stop():
    pos = _pos()  # 진입 100
    ind = _ind(close=96.0, sma20=80, sma60=70, senkou_a=60, senkou_b=55)
    res = evaluate_exit(pos, ind)  # -4% ≤ -3%
    assert res.action == ExitAction.FULL_EXIT
    assert "하드스탑" in res.reason


def test_exit_ma60_break_stop():
    pos = _pos()
    # 손실 -2% (하드스탑 미발동), 가격 < MA60
    ind = _ind(close=98.0, sma20=97, sma60=99, senkou_a=90, senkou_b=88)
    res = evaluate_exit(pos, ind)
    assert res.action == ExitAction.FULL_EXIT
    assert "MA60" in res.reason


def test_exit_cloud_top_break():
    pos = _pos()
    # MA60 위지만 구름 상단 아래
    ind = _ind(close=101.0, sma20=99, sma60=100, senkou_a=102, senkou_b=101)
    res = evaluate_exit(pos, ind)
    assert res.action == ExitAction.FULL_EXIT
    assert "구름" in res.reason


def test_exit_partial_2r():
    pos = _pos()  # 1R = 10, 2R 목표 = 120
    ind = _ind(close=121.0, sma20=105, sma60=100, senkou_a=110, senkou_b=108)
    res = evaluate_exit(pos, ind)
    assert res.action == ExitAction.PARTIAL_EXIT
    assert res.quantity == pytest.approx(1.0)  # 초기 2.0 의 50%


def test_exit_full_3r():
    pos = _pos()
    pos.partial_taken = True
    pos.quantity = 1.0
    ind = _ind(close=131.0, sma20=110, sma60=105, senkou_a=115, senkou_b=112)  # 3R=130
    res = evaluate_exit(pos, ind)
    assert res.action == ExitAction.FULL_EXIT
    assert "3R" in res.reason


def test_exit_hold():
    pos = _pos()
    # 소폭 이익, 모든 청산 조건 미충족
    ind = _ind(close=105.0, sma20=101, sma60=99, senkou_a=103, senkou_b=102)
    res = evaluate_exit(pos, ind)
    assert res.action == ExitAction.HOLD
