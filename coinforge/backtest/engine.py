"""BacktestEngine — 과거 4H 봉을 순회하며 실전과 동일한 전략·리스크 로직 실행.

AGENTS.md §9: 백테스트는 strategy·risk 와 동일 패키지를 import 해 로직 드리프트를
방지한다. 여기서는 Orchestrator 를 Mock 거래소/저장소/알림으로 구동해 재사용한다.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..config import Config
from ..domain.candle import Candle
from ..domain.trade import TradeLog
from ..engine.orchestrator import Orchestrator
from ..exchange.mock import MockExchange
from ..indicators.engine import InsufficientCandlesError
from ..notify.mock import MockNotifier
from ..storage.memory import InMemoryRepository
from .metrics import PerformanceMetrics, compute_metrics, passes_gate


@dataclass
class BacktestReport:
    metrics: PerformanceMetrics
    gate_passed: bool
    gate_reason: str
    trade_logs: list[TradeLog] = field(default_factory=list)
    equity_curve: list[float] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "metrics": self.metrics.as_dict(),
            "gate_passed": self.gate_passed,
            "gate_reason": self.gate_reason,
            "num_trade_logs": len(self.trade_logs),
        }


class _SlidingProvider:
    """백테스트용 캔들 공급자: 현재 인덱스까지의 캔들만 노출."""

    def __init__(self, candles: list[Candle]) -> None:
        self._all = candles
        self._end = 0

    def set_end(self, end: int) -> None:
        self._end = end

    def get_candles(self, count: int) -> list[Candle]:
        window = self._all[: self._end]
        if len(window) < count:
            raise RuntimeError(f"백테스트 캔들 부족: {len(window)} < {count}")
        return window[-count:]


class BacktestEngine:
    def __init__(self, candles: list[Candle], config: Config) -> None:
        self.candles = sorted(candles, key=lambda c: c.datetime)
        self.config = config

    def run(self) -> BacktestReport:
        count = self.config.candle_count
        initial_equity = self.config.total_equity_krw

        provider = _SlidingProvider(self.candles)
        exchange = MockExchange(
            krw=initial_equity, btc=0.0, market=self.config.market,
            slippage_bp=self.config.slippage_bp,
        )
        repo = InMemoryRepository()
        notifier = MockNotifier()
        orch = Orchestrator(
            config=self.config,
            candle_provider=provider,
            exchange=exchange,
            repository=repo,
            notifier=notifier,
        )

        equity_curve: list[float] = []
        for i in range(count, len(self.candles) + 1):
            provider.set_end(i)
            current = self.candles[i - 1]
            exchange.set_price(current.close)
            try:
                orch.run_cycle(now=current.datetime)
            except InsufficientCandlesError:
                continue
            equity_curve.append(exchange.equity_krw)

        trade_logs = repo.list_trade_logs(limit=10_000)
        metrics = compute_metrics(trade_logs, equity_curve, initial_equity)
        gate_passed, gate_reason = passes_gate(metrics)
        return BacktestReport(
            metrics=metrics,
            gate_passed=gate_passed,
            gate_reason=gate_reason,
            trade_logs=trade_logs,
            equity_curve=equity_curve,
        )
