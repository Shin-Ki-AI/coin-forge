"""FastAPI 앱 — 대시보드 + 차트·신호·포지션·거래·상태·백테스트 API.

fastapi 는 선택 의존(`pip install .[api]`). create_app 호출 시 import 한다.
운영 관찰이 목적이므로 /api/signal 은 주문 없이 현재 신호를 진단한다.
"""

from __future__ import annotations

import time
from datetime import date
from pathlib import Path

from ..config import Config, load_config
from ..domain.candle import candles_to_dataframe
from ..factory import build_candle_provider, build_repository
from ..indicators.engine import compute_indicator_frame
from ..risk.manager import RiskManager
from ..strategy import build_market_state, evaluate_signal

_STATIC = Path(__file__).parent / "static"


class _CandleCache:
    """짧은 TTL 캔들 캐시 — 업비트 rate limit 보호 (여러 엔드포인트 공유)."""

    def __init__(self, provider, count: int, ttl: float = 30.0) -> None:
        self._provider = provider
        self._count = count
        self._ttl = ttl
        self._at = 0.0
        self._candles = None

    def get(self):
        now = time.time()
        if self._candles is None or now - self._at > self._ttl:
            self._candles = self._provider.get_candles(self._count)
            self._at = now
        return self._candles


def create_app(config: Config | None = None):
    from fastapi import FastAPI, HTTPException
    from fastapi.responses import FileResponse

    config = config or load_config()
    app = FastAPI(title="Coin Forge API", version="0.1.0")

    provider = build_candle_provider(config)
    repo = build_repository(config)
    risk = RiskManager(config)
    cache = _CandleCache(provider, config.candle_count)

    from ..paper import PaperEngine
    paper = PaperEngine(config, provider)
    app.state.paper_engine = paper  # cli/api.py 가 백그라운드 스케줄러로 접근

    # --- 대시보드 (정적 SPA) ---
    @app.get("/")
    def dashboard():  # noqa: ANN202
        return FileResponse(_STATIC / "dashboard.html")

    # --- 차트 데이터 (11.1.1) ---
    @app.get("/api/candles")
    def get_candles():  # noqa: ANN202
        candles = cache.get()
        frame = compute_indicator_frame(candles_to_dataframe(candles)).reset_index()
        records = []
        for _, r in frame.iterrows():
            records.append({
                "datetime": r["datetime"].isoformat(),
                "open": r["open"], "high": r["high"], "low": r["low"],
                "close": r["close"], "volume": r["volume"],
                "sma20": _n(r["sma20"]), "sma60": _n(r["sma60"]), "sma200": _n(r["sma200"]),
                "senkou_a": _n(r["senkou_a"]), "senkou_b": _n(r["senkou_b"]),
            })
        return {"market": config.market, "candles": records}

    # --- 신호 진단 (운영 관찰 핵심) ---
    @app.get("/api/signal")
    def get_signal():  # noqa: ANN202
        candles = cache.get()
        state = build_market_state(candles)
        pos = repo.get_open_position(config.market)
        diag = evaluate_signal(state, pos)
        ind = state.indicators
        return {
            "market": config.market,
            "datetime": ind.datetime.isoformat(),
            "price": ind.close,
            "indicators": {
                "sma20": ind.sma20, "sma60": ind.sma60, "sma200": ind.sma200,
                "cloud_top": ind.cloud_top, "cloud_bottom": ind.cloud_bottom,
                "cloud_color": ind.cloud_color.value,
                "volume": ind.volume, "volume_avg20": ind.volume_avg20,
            },
            "has_position": pos is not None,
            "signal": diag.as_dict(),
        }

    # --- 현재 포지션 (11.1.2) ---
    @app.get("/api/position")
    def get_position():  # noqa: ANN202
        pos = repo.get_open_position(config.market)
        if not pos:
            return {"position": None}
        price = cache.get()[-1].close
        d = pos.to_dict()
        d.update({
            "target_2r": pos.target_2r, "target_3r": pos.target_3r,
            "risk_per_unit": pos.risk_per_unit,
            "unrealized_pnl_pct": pos.unrealized_pnl_pct(price),
            "r_multiple": pos.r_multiple(price),
            "current_price": price,
        })
        return {"position": d}

    # --- 거래 이력 (11.1.3) ---
    @app.get("/api/trades")
    def get_trades(limit: int = 100):  # noqa: ANN202
        return {"trades": [t.to_dict() for t in repo.list_trade_logs(limit=limit)]}

    # --- 서킷 브레이커·일일 PnL (11.1.4) ---
    @app.get("/api/status")
    def get_status():  # noqa: ANN202
        daily_loss = repo.get_daily_loss(date.today())
        pos = repo.get_open_position(config.market)
        halt = risk.check_trading_allowed(
            has_open_position=pos is not None,
            daily_loss_krw=daily_loss, equity_krw=config.total_equity_krw,
        )
        return {
            "market": config.market, "mode": config.trading_mode.value,
            "total_equity_krw": config.total_equity_krw,
            "daily_loss_krw": daily_loss,
            "daily_loss_limit_pct": config.daily_loss_limit_pct,
            "trading_halted": halt.halted, "halt_reason": halt.reason,
            "has_position": pos is not None,
            "sizing_mode": config.sizing_mode,
            "max_position_pct": config.max_position_pct,
            "fixed_position_pct": config.fixed_position_pct,
        }

    # --- 모의투자 (#1): 지금부터 실시간 누적되는 모의계좌 ---
    @app.get("/api/paper")
    def get_paper():  # noqa: ANN202
        return paper.snapshot()

    @app.post("/api/paper/step")
    def step_paper():  # noqa: ANN202
        """한 4H 사이클 전진 (대기 없이 즉시 실행 — 데모·수동 진행용)."""
        result = paper.step()
        snap = paper.snapshot()
        snap["last_action"] = result.action
        snap["last_reason"] = result.reason
        return snap

    @app.post("/api/paper/reset")
    def reset_paper(starting_equity: float | None = None):  # noqa: ANN202
        paper.reset(starting_equity)
        return paper.snapshot()

    # --- 온디맨드 백테스트 (전략 개선 진단) ---
    @app.get("/api/backtest")
    def run_backtest(bars: int = 1500):  # noqa: ANN202
        from ..backtest.engine import BacktestEngine

        bars = max(config.candle_count + 50, min(bars, 5000))
        candles = provider.get_candles(bars)
        report = BacktestEngine(candles, config).run()
        d = report.as_dict()
        d["period"] = {
            "from": candles[0].datetime.isoformat(),
            "to": candles[-1].datetime.isoformat(),
            "bars": len(candles),
        }
        d["equity_curve"] = report.equity_curve
        return d

    # --- 기법 비교 (#2): 여러 전략 설정을 같은 기간으로 백테스트해 순위화 ---
    @app.get("/api/compare")
    def compare(bars: int = 1500):  # noqa: ANN202
        from ..backtest.compare import PRESETS, compare_configs

        bars = max(config.candle_count + 50, min(bars, 5000))
        candles = provider.get_candles(bars)
        ranked = compare_configs(candles, config, PRESETS)
        return {
            "period": {
                "from": candles[0].datetime.isoformat(),
                "to": candles[-1].datetime.isoformat(),
                "bars": len(candles),
            },
            "results": ranked,
        }

    return app


def _n(v):
    import math

    return None if v is None or (isinstance(v, float) and math.isnan(v)) else float(v)
