"""리스크 관리 단위 테스트 (CHECKLIST 6.6). 경계값 포함."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from coinforge.config import Config
from coinforge.domain.indicators import Indicators
from coinforge.risk import RiskManager, compute_stop_price


def _cfg(**overrides) -> Config:
    base = dict(
        RISK_PER_TRADE_PCT=0.01,
        DAILY_LOSS_LIMIT_PCT=0.03,
        HARD_STOP_PCT=0.03,
        MAX_POSITION_PCT=1.0,  # 기존 테스트는 상한 없이 순수 공식 검증
    )
    base.update(overrides)
    return Config(**base)


def _ind(close=10_000_000.0, sma60=9_800_000.0, senkou_a=9_700_000.0, senkou_b=9_600_000.0):
    return Indicators(
        datetime=datetime(2026, 1, 1, tzinfo=timezone.utc),
        close=close,
        sma20=9_900_000.0,
        sma60=sma60,
        sma200=9_500_000.0,
        senkou_a=senkou_a,
        senkou_b=senkou_b,
        volume=100.0,
        volume_avg20=90.0,
    )


def test_stop_price_is_higher_support():
    ind = _ind()
    # max(MA60=9.8M, 구름상단=9.7M) = 9.8M
    assert compute_stop_price(ind.close, ind) == pytest.approx(9_800_000.0)


def test_one_percent_rule_sizing():
    rm = RiskManager(_cfg())
    ind = _ind()
    entry = ind.close
    s = rm.compute_sizing(
        entry_price=entry, ind=ind, equity_krw=100_000_000, available_krw=100_000_000
    )
    assert s.ok
    # risk = 1% of 100M = 1,000,000 ; risk_per_unit = 10M-9.8M = 200,000
    assert s.risk_krw == pytest.approx(1_000_000)
    assert s.risk_per_unit == pytest.approx(200_000)
    assert s.quantity == pytest.approx(5.0)  # 1,000,000 / 200,000


def test_sizing_capped_by_balance():
    rm = RiskManager(_cfg())
    ind = _ind()
    # 가용 잔고가 부족 → 수량 축소
    s = rm.compute_sizing(
        entry_price=ind.close, ind=ind, equity_krw=100_000_000, available_krw=10_000_000
    )
    assert s.ok
    assert s.balance_limited
    # 수수료 여유를 남기고 잔고 이내로 축소 (fee_buffer=0.001)
    assert s.notional_krw <= 10_000_000
    assert s.notional_krw == pytest.approx(10_000_000 / 1.001, rel=1e-6)


def test_max_position_cap_prevents_allin():
    # 손절이 진입가 0.5% 이내로 가까우면 1% 룰 수량이 자본을 초과 → 상한(30%)으로 제한
    rm = RiskManager(_cfg(MAX_POSITION_PCT=0.30))
    ind = _ind(sma60=9_950_000.0)  # risk_per_unit = 50,000 (0.5%)
    s = rm.compute_sizing(
        entry_price=ind.close, ind=ind, equity_krw=100_000_000, available_krw=100_000_000
    )
    assert s.ok
    assert s.equity_capped          # 비중 상한 발동
    assert not s.balance_limited    # 잔고는 충분(상한이 먼저 물림)
    assert s.notional_krw == pytest.approx(30_000_000)  # 자본의 30%
    assert s.quantity == pytest.approx(3.0)             # 30M / 10M
    # 상한 없었으면 20 BTC(200M, 200% 올인)였을 것
    assert "비중 상한" in s.reason


def test_fixed_fraction_mode():
    # 고정 비율 모드: 손절거리와 무관하게 자본의 20%를 주문금액으로
    rm = RiskManager(_cfg(SIZING_MODE="fixed", FIXED_POSITION_PCT=0.20))
    ind = _ind()
    s = rm.compute_sizing(
        entry_price=ind.close, ind=ind, equity_krw=100_000_000, available_krw=100_000_000
    )
    assert s.ok
    assert s.notional_krw == pytest.approx(20_000_000)  # 자본의 20%
    assert s.quantity == pytest.approx(2.0)             # 20M / 10M
    assert "고정 비율" in s.reason


def test_sizing_rejects_zero_balance():
    rm = RiskManager(_cfg())
    ind = _ind()
    s = rm.compute_sizing(
        entry_price=ind.close, ind=ind, equity_krw=100_000_000, available_krw=0.0
    )
    assert not s.ok


def test_circuit_breaker_daily_loss_boundary():
    rm = RiskManager(_cfg())
    equity = 100_000_000
    # 정확히 3% = 3,000,000 → 중단 (경계값 포함)
    halt = rm.check_trading_allowed(
        has_open_position=False, daily_loss_krw=3_000_000, equity_krw=equity
    )
    assert halt.halted


def test_circuit_breaker_below_limit_allows():
    rm = RiskManager(_cfg())
    halt = rm.check_trading_allowed(
        has_open_position=False, daily_loss_krw=2_999_999, equity_krw=100_000_000
    )
    assert not halt.halted


def test_circuit_breaker_blocks_existing_position():
    rm = RiskManager(_cfg())
    halt = rm.check_trading_allowed(
        has_open_position=True, daily_loss_krw=0, equity_krw=100_000_000
    )
    assert halt.halted
