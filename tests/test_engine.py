"""오케스트레이터 E2E 테스트 (CHECKLIST 12.1 부분)."""

from __future__ import annotations

from datetime import timedelta

import numpy as np

from coinforge.bridge.mock import MockCandleProvider
from coinforge.config import Config
from coinforge.constants import TIMEFRAME_MINUTES
from coinforge.domain.candle import Candle
from coinforge.engine.orchestrator import Orchestrator
from coinforge.exchange.mock import MockExchange
from coinforge.notify.mock import MockNotifier
from coinforge.storage.memory import InMemoryRepository

from .fixtures import linear_uptrend, make_candles


def _entry_candles() -> list[Candle]:
    closes = linear_uptrend(240, start=50_000_000, step=30_000)
    lows = [c * 0.995 for c in closes]
    ma20_prev = float(np.mean(closes[-21:-1]))
    lows[-2] = ma20_prev * 0.999  # 직전 봉 MA20 터치 유도
    return make_candles(closes, lows=lows)


def _build():
    config = Config(TRADING_MODE="paper", TOTAL_EQUITY_KRW=100_000_000)
    exchange = MockExchange(krw=100_000_000, btc=0.0)
    repo = InMemoryRepository()
    notifier = MockNotifier()
    candles = _entry_candles()
    provider = MockCandleProvider(candles)
    orch = Orchestrator(
        config=config, candle_provider=provider, exchange=exchange,
        repository=repo, notifier=notifier,
    )
    return orch, provider, exchange, repo, notifier, candles


def test_cycle_opens_position_on_signal():
    orch, provider, exchange, repo, notifier, candles = _build()
    result = orch.run_cycle(now=candles[-1].datetime)
    assert result.action == "entry", result.reason
    pos = repo.get_open_position("KRW-BTC")
    assert pos is not None
    assert pos.quantity > 0
    assert pos.stop_price < pos.entry_price
    assert notifier.events[-1].type == "entry"


def test_cycle_exits_on_crash():
    orch, provider, exchange, repo, notifier, candles = _build()
    orch.run_cycle(now=candles[-1].datetime)          # 진입
    assert repo.get_open_position("KRW-BTC") is not None

    # 급락 캔들 추가 → MA60/하드스탑 손절 유발
    last = candles[-1]
    crash_close = last.close * 0.90
    crash = Candle(
        datetime=last.datetime + timedelta(minutes=TIMEFRAME_MINUTES),
        open=last.close, high=last.close, low=crash_close, close=crash_close,
        volume=100.0,
    )
    provider.set_candles(candles + [crash])
    exchange.set_price(crash_close)

    result = orch.run_cycle(now=crash.datetime)
    assert result.action == "exit", result.reason
    assert repo.get_open_position("KRW-BTC") is None
    assert notifier.events[-1].type == "exit"
    assert notifier.events[-1].pnl_percent is not None


def test_no_entry_when_position_open_blocks_second_entry():
    orch, provider, exchange, repo, notifier, candles = _build()
    orch.run_cycle(now=candles[-1].datetime)  # 진입
    # 같은 신호 캔들로 재실행 → 포지션 보유 분기(청산 평가)로 진입 차단
    result = orch.run_cycle(now=candles[-1].datetime)
    assert result.action in ("hold", "exit", "partial_exit")
