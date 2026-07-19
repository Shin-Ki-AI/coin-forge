"""PaperEngine 모의투자 엔진 테스트 (#1).

시작 자본에서 출발해 step() 마다 자산곡선이 쌓이고, JSON으로 영속화되어
재시작(새 엔진 인스턴스)해도 누적이 유지되는지 검증한다.
"""

from __future__ import annotations

from datetime import datetime, timezone

from coinforge.config import Config
from coinforge.paper import PaperEngine

from .fixtures import linear_uptrend, make_candles

NOW = datetime(2026, 7, 13, 12, 0, tzinfo=timezone.utc)


class _Provider:
    def __init__(self, candles):
        self._c = candles

    def get_candles(self, count):
        if len(self._c) < count:
            raise RuntimeError(f"few: {len(self._c)} < {count}")
        return self._c[-count:]


def _engine(tmp_path, **cfg):
    base = dict(TRADING_MODE="paper", TOTAL_EQUITY_KRW=100_000_000, MAX_POSITION_PCT=0.30)
    base.update(cfg)
    config = Config(**base)
    candles = make_candles(linear_uptrend(300, start=50_000_000, step=40_000))
    path = str(tmp_path / "paper.json")
    return PaperEngine(config, _Provider(candles), path=path, clock=lambda: NOW), path


def test_fresh_account_starts_at_capital(tmp_path):
    eng, _ = _engine(tmp_path)
    snap = eng.snapshot()
    assert snap["starting_equity"] == 100_000_000
    assert snap["current_equity"] == 100_000_000
    assert snap["cycles"] == 0
    assert snap["return_pct"] == 0.0


def test_step_appends_equity_snapshot_and_persists(tmp_path):
    eng, path = _engine(tmp_path)
    eng.step()
    snap = eng.snapshot()
    assert snap["cycles"] == 1
    assert snap["current_equity"] > 0
    # 파일로 저장됨
    import os
    assert os.path.exists(path)


def test_state_persists_across_restart(tmp_path):
    eng, path = _engine(tmp_path)
    eng.step()
    eng.step()
    assert eng.snapshot()["cycles"] == 2

    # 같은 경로로 새 엔진 → 누적 유지
    config = eng.config
    reloaded = PaperEngine(config, eng.provider, path=path, clock=lambda: NOW)
    assert reloaded.snapshot()["cycles"] == 2
    assert reloaded.state.started_at == eng.state.started_at


def test_reset_restarts_from_capital(tmp_path):
    eng, _ = _engine(tmp_path)
    eng.step()
    eng.reset()
    snap = eng.snapshot()
    assert snap["cycles"] == 0
    assert snap["current_equity"] == 100_000_000
    assert snap["position"] is None


def test_equity_stays_near_capital_on_uptrend(tmp_path):
    # 진입이 나더라도 슬리피지·수수료 이상으로 자산이 튀지 않아야 함
    eng, _ = _engine(tmp_path)
    for _ in range(3):
        eng.step()
    eq = eng.snapshot()["current_equity"]
    assert 0.9 * 100_000_000 < eq < 1.1 * 100_000_000
