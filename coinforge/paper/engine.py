"""PaperEngine — JSON 영속 모의계좌를 4H 사이클마다 전진시킨다 (#1).

상태(현금·보유·포지션·거래·자산곡선)를 파일에 저장하므로 프로세스를 재시작해도
누적이 유지된다. step() 한 번 = 한 4H 사이클. 실거래와 같은 Orchestrator를 돌린다.
"""

from __future__ import annotations

import json
import logging
import threading
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Callable, Optional

from ..config import Config
from ..domain.position import Position
from ..engine.orchestrator import CycleResult, Orchestrator
from ..exchange.mock import MockExchange
from ..notify.mock import MockNotifier
from ..storage.memory import InMemoryRepository

log = logging.getLogger(__name__)


@dataclass
class PaperState:
    """직렬화 가능한 모의계좌 상태."""

    started_at: str
    starting_equity: float
    cash_krw: float
    btc: float
    position: Optional[dict] = None
    trades: list = field(default_factory=list)          # TradeLog.to_dict() 목록
    daily_pnl: dict = field(default_factory=dict)        # 'YYYY-MM-DD' -> 순손익(KRW)
    equity_curve: list = field(default_factory=list)     # {"t": iso, "equity": float}
    last_cycle_at: Optional[str] = None

    @classmethod
    def fresh(cls, starting_equity: float, now: datetime) -> "PaperState":
        return cls(
            started_at=now.isoformat(),
            starting_equity=starting_equity,
            cash_krw=starting_equity,
            btc=0.0,
        )

    @classmethod
    def from_dict(cls, d: dict) -> "PaperState":
        known = {f: d[f] for f in cls.__dataclass_fields__ if f in d}
        return cls(**known)


class PaperEngine:
    """모의계좌를 로드·전진·저장한다. 스레드 안전(step/reset 직렬화)."""

    def __init__(
        self,
        config: Config,
        provider,
        path: Optional[str] = None,
        clock: Optional[Callable[[], datetime]] = None,
    ) -> None:
        self.config = config
        self.provider = provider
        self.path = Path(path or config.paper_state_path)
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._lock = threading.Lock()
        self.state = self._load()

    # --- 영속 -----------------------------------------------------------------
    def _load(self) -> PaperState:
        if self.path.exists():
            try:
                return PaperState.from_dict(json.loads(self.path.read_text(encoding="utf-8")))
            except (json.JSONDecodeError, TypeError, KeyError) as exc:
                log.warning("모의계좌 상태 로드 실패(%s) — 새로 시작", exc)
        return PaperState.fresh(self.config.total_equity_krw, self._clock())

    def _save(self) -> None:
        self.path.write_text(
            json.dumps(asdict(self.state), ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def reset(self, starting_equity: Optional[float] = None) -> PaperState:
        with self._lock:
            eq = starting_equity if starting_equity is not None else self.config.total_equity_krw
            self.state = PaperState.fresh(eq, self._clock())
            self._save()
            return self.state

    # --- 한 사이클 전진 -------------------------------------------------------
    def step(self, now: Optional[datetime] = None) -> CycleResult:
        with self._lock:
            now = now or self._clock()
            exchange = MockExchange(
                krw=self.state.cash_krw, btc=self.state.btc,
                market=self.config.market, slippage_bp=self.config.slippage_bp,
            )
            repo = InMemoryRepository()
            if self.state.position:
                repo.save_position(Position.from_dict(self.state.position))
            # 서킷 브레이커용 당일 실현손익 시드
            for k, v in self.state.daily_pnl.items():
                repo.add_realized_pnl(date.fromisoformat(k), v)

            orch = Orchestrator(
                config=self.config, candle_provider=self.provider,
                exchange=exchange, repository=repo, notifier=MockNotifier(),
            )
            result = orch.run_cycle(now=now)

            # 상태 반영
            bal = exchange.get_balance()
            self.state.cash_krw = bal.krw
            self.state.btc = bal.btc
            pos = repo.get_open_position(self.config.market)
            self.state.position = pos.to_dict() if pos else None

            for t in repo.list_trade_logs(limit=10_000):
                self.state.trades.append(t.to_dict())
                if t.pnl_krw is not None:
                    k = t.timestamp.date().isoformat()
                    self.state.daily_pnl[k] = self.state.daily_pnl.get(k, 0.0) + t.pnl_krw

            price = exchange.get_price(self.config.market)
            if price <= 0:  # 사이클이 가격 설정 전에 종료된 경우 대비
                price = self._last_price_fallback()
            equity = bal.krw + bal.btc * price
            self.state.equity_curve.append({"t": now.isoformat(), "equity": equity})
            self.state.last_cycle_at = now.isoformat()
            self._save()
            return result

    def _last_price_fallback(self) -> float:
        try:
            return self.provider.get_candles(self.config.candle_count)[-1].close
        except Exception:  # noqa: BLE001 — 폴백은 실패해도 0 처리
            return 0.0

    # --- 조회 (API/대시보드용) ------------------------------------------------
    def snapshot(self) -> dict:
        curve = self.state.equity_curve
        current_equity = curve[-1]["equity"] if curve else self.state.starting_equity
        base = self.state.starting_equity or 1.0
        return {
            "started_at": self.state.started_at,
            "last_cycle_at": self.state.last_cycle_at,
            "starting_equity": self.state.starting_equity,
            "current_equity": current_equity,
            "return_pct": current_equity / base - 1.0,
            "cash_krw": self.state.cash_krw,
            "btc": self.state.btc,
            "position": self.state.position,
            "cycles": len(curve),
            "equity_curve": curve,
            "trades": self.state.trades[-200:],
        }
