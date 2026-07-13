"""성과 지표 — 승률, Profit Factor, MDD 및 배포 게이트 (CHECKLIST 10.3~10.6)."""

from __future__ import annotations

from dataclasses import dataclass, field

from ..domain.trade import TradeLog, TradeType

# 배포 게이트 (PLAN.md 백테스트 기준)
MIN_WIN_RATE = 0.45
MIN_PROFIT_FACTOR = 1.5


@dataclass
class PerformanceMetrics:
    total_trades: int = 0
    wins: int = 0
    losses: int = 0
    win_rate: float = 0.0
    gross_profit: float = 0.0     # 이익 합 (KRW)
    gross_loss: float = 0.0       # 손실 합 (양수, KRW)
    profit_factor: float = 0.0
    max_drawdown: float = 0.0     # 최대 낙폭 (비율)
    net_pnl: float = 0.0
    final_equity: float = 0.0
    return_pct: float = 0.0

    def as_dict(self) -> dict:
        return {
            "total_trades": self.total_trades,
            "wins": self.wins,
            "losses": self.losses,
            "win_rate": round(self.win_rate, 4),
            "gross_profit": round(self.gross_profit, 2),
            "gross_loss": round(self.gross_loss, 2),
            "profit_factor": round(self.profit_factor, 4),
            "max_drawdown": round(self.max_drawdown, 4),
            "net_pnl": round(self.net_pnl, 2),
            "final_equity": round(self.final_equity, 2),
            "return_pct": round(self.return_pct, 4),
        }


def _max_drawdown(equity_curve: list[float]) -> float:
    """최대 낙폭 (peak 대비 최대 하락 비율)."""
    peak = float("-inf")
    mdd = 0.0
    for v in equity_curve:
        peak = max(peak, v)
        if peak > 0:
            dd = (peak - v) / peak
            mdd = max(mdd, dd)
    return mdd


def compute_metrics(
    trade_logs: list[TradeLog],
    equity_curve: list[float],
    initial_equity: float,
) -> PerformanceMetrics:
    """거래 로그를 포지션 단위로 묶어 성과 지표를 계산한다.

    한 포지션(position_id)의 모든 청산(부분+전량)의 pnl_krw 합 = 해당 거래 손익.
    """
    pnl_by_position: dict[str, float] = {}
    for log in trade_logs:
        if log.trade_type in (TradeType.EXIT, TradeType.PARTIAL_EXIT) and log.pnl_krw is not None:
            pnl_by_position[log.position_id] = pnl_by_position.get(log.position_id, 0.0) + log.pnl_krw

    trade_pnls = list(pnl_by_position.values())
    wins = [p for p in trade_pnls if p > 0]
    losses = [p for p in trade_pnls if p <= 0]

    gross_profit = sum(wins)
    gross_loss = -sum(losses)
    total = len(trade_pnls)

    win_rate = len(wins) / total if total else 0.0
    if gross_loss > 0:
        profit_factor = gross_profit / gross_loss
    else:
        profit_factor = float("inf") if gross_profit > 0 else 0.0

    final_equity = equity_curve[-1] if equity_curve else initial_equity
    return PerformanceMetrics(
        total_trades=total,
        wins=len(wins),
        losses=len(losses),
        win_rate=win_rate,
        gross_profit=gross_profit,
        gross_loss=gross_loss,
        profit_factor=profit_factor,
        max_drawdown=_max_drawdown(equity_curve or [initial_equity]),
        net_pnl=sum(trade_pnls),
        final_equity=final_equity,
        return_pct=(final_equity - initial_equity) / initial_equity if initial_equity else 0.0,
    )


def passes_gate(m: PerformanceMetrics) -> tuple[bool, str]:
    """배포 게이트 판정 (10.4, 10.5). 미달 시 실거래 배포 차단."""
    reasons = []
    if m.win_rate < MIN_WIN_RATE:
        reasons.append(f"승률 {m.win_rate:.1%} < {MIN_WIN_RATE:.0%}")
    if m.profit_factor < MIN_PROFIT_FACTOR:
        reasons.append(f"손익비 {m.profit_factor:.2f} < {MIN_PROFIT_FACTOR}")
    if reasons:
        return False, "배포 차단: " + ", ".join(reasons)
    return True, "게이트 통과 (승률·손익비 기준 충족)"
