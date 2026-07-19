"""전략 설정 비교 (#2) — 여러 StrategyParams 를 같은 캔들로 백테스트해 순위화.

배포 게이트(승률 45%·손익비 1.5)를 통과하는 설정을 우선, 그다음 손익비·승률 순으로
정렬한다. 개별 설정이 실패(예: 이평선 기간이 봉 수보다 큼)해도 전체는 죽지 않는다.
"""

from __future__ import annotations

from dataclasses import asdict

from ..config import Config
from ..domain.candle import Candle
from ..strategy.params import StrategyParams
from .engine import BacktestEngine

# 대시보드 기본 비교 프리셋 (이름 → 파라미터)
PRESETS: dict[str, StrategyParams] = {
    "기본 (20/60/200)": StrategyParams(),
    "빠른 MA (10/30/120)": StrategyParams(ma_short=10, ma_mid=30, ma_long=120),
    "느린 MA (30/90/200)": StrategyParams(ma_short=30, ma_mid=90, ma_long=200),
    "눌림목 없이": StrategyParams(require_pullback=False),
    "거래량 필수": StrategyParams(require_volume=True),
    "익절 넓게 (3R/5R)": StrategyParams(partial_take_r=3.0, full_take_r=5.0),
}


def _rank_key(r: dict):
    if not r["ok"]:
        return (-1.0, -1.0, -1.0)
    m = r["metrics"]
    pf = m.get("profit_factor")
    pf = min(pf, 1e9) if pf is not None else 0.0
    return (1.0 if r["gate_passed"] else 0.0, pf, m.get("win_rate", 0.0))


def compare_configs(
    candles: list[Candle], config: Config, named_params: dict[str, StrategyParams]
) -> list[dict]:
    """각 설정을 백테스트해 순위 매긴 결과 목록을 반환한다."""
    results: list[dict] = []
    for name, params in named_params.items():
        try:
            report = BacktestEngine(candles, config, params=params).run()
            results.append({
                "name": name,
                "ok": True,
                "gate_passed": report.gate_passed,
                "gate_reason": report.gate_reason,
                "metrics": report.metrics.as_dict(),
                "params": asdict(params),
            })
        except Exception as exc:  # noqa: BLE001 — 한 설정 실패가 전체를 막지 않게
            results.append({"name": name, "ok": False, "error": str(exc)})

    ok = sorted([r for r in results if r["ok"]], key=_rank_key, reverse=True)
    bad = [r for r in results if not r["ok"]]
    for i, r in enumerate(ok):
        r["rank"] = i + 1
    return ok + bad
