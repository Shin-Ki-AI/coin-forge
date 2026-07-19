"""신호 진단 — 현재 시점의 진입 3관문·방어·청산 상태를 주문 없이 평가.

대시보드/운영 관찰용. 실제 매매 분기(orchestrator)와 동일한 조건을 사용하되,
'왜' 진입/대기/차단인지 관문별로 분해해 노출한다.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from ..domain.indicators import Indicators
from ..domain.position import Position
from .context import MarketState
from .defense import evaluate_defense
from .exit import evaluate_exit
from .pullback import detect_pullback


@dataclass
class GateStatus:
    name: str
    passed: bool
    detail: str

    def as_dict(self) -> dict:
        return {"name": self.name, "passed": self.passed, "detail": self.detail}


@dataclass
class SignalDiagnostics:
    decision: str            # "entry" | "blocked" | "wait" | "exit" | "partial_exit" | "hold"
    headline: str            # 사람이 읽는 한 줄 요약
    gates: list[GateStatus] = field(default_factory=list)
    defense_blocked: bool = False
    defense_reason: str = ""
    volume_confirmed: bool = False
    exit_action: Optional[str] = None
    exit_reason: Optional[str] = None

    def as_dict(self) -> dict:
        return {
            "decision": self.decision,
            "headline": self.headline,
            "gates": [g.as_dict() for g in self.gates],
            "defense_blocked": self.defense_blocked,
            "defense_reason": self.defense_reason,
            "volume_confirmed": self.volume_confirmed,
            "exit_action": self.exit_action,
            "exit_reason": self.exit_reason,
        }


def _won(v: float) -> str:
    return f"{v:,.0f}"


def evaluate_signal(
    state: MarketState, position: Optional[Position] = None, params=None
) -> SignalDiagnostics:
    """현재 시장 상태로 매매 의사결정을 진단한다 (주문 없음)."""
    from .params import DEFAULT_PARAMS

    p = params or DEFAULT_PARAMS
    ind: Indicators = state.indicators

    # 포지션 보유 시: 청산 관점
    if position is not None:
        exit_res = evaluate_exit(position, ind, p)
        gates = _exit_gates(position, ind)
        if exit_res.action.value == "hold":
            return SignalDiagnostics(
                decision="hold",
                headline="포지션 보유 중 — 청산 조건 미충족, 보유 유지",
                gates=gates,
                exit_action="hold",
                exit_reason=exit_res.reason,
            )
        return SignalDiagnostics(
            decision=exit_res.action.value,
            headline=f"청산 신호: {exit_res.reason}",
            gates=gates,
            exit_action=exit_res.action.value,
            exit_reason=exit_res.reason,
        )

    # 무포지션: 방어 → 진입 관문
    defense = evaluate_defense(ind, None)
    gates = _entry_gates(state, p)

    if defense.blocked:
        return SignalDiagnostics(
            decision="blocked",
            headline=f"매수 차단(방어): {defense.reason}",
            gates=gates,
            defense_blocked=True,
            defense_reason=defense.reason,
            volume_confirmed=ind.volume_above_avg,
        )

    all_pass = all(g.passed for g in gates)
    if all_pass:
        vol = " · 거래량 확인(신뢰도↑)" if ind.volume_above_avg else ""
        return SignalDiagnostics(
            decision="entry",
            headline=f"진입 신호 발생 — 진입 조건 통과{vol}",
            gates=gates,
            volume_confirmed=ind.volume_above_avg,
        )

    failed = next(g for g in gates if not g.passed)
    return SignalDiagnostics(
        decision="wait",
        headline=f"대기 — {failed.name} 미충족",
        gates=gates,
        volume_confirmed=ind.volume_above_avg,
    )


def _entry_gates(state: MarketState, params=None) -> list[GateStatus]:
    """활성화된 관문만 상태로 반환한다(params 의 require_* 토글 반영)."""
    from .params import DEFAULT_PARAMS

    p = params or DEFAULT_PARAMS
    ind = state.indicators
    gates: list[GateStatus] = []

    if p.require_cloud:
        g1 = ind.above_cloud and ind.is_bull_cloud
        gates.append(GateStatus(
            "1관문 · 장기 환경", g1,
            f"가격 {_won(ind.close)} vs 구름상단 {_won(ind.cloud_top)} · "
            f"구름 {'상승' if ind.is_bull_cloud else '하락'}",
        ))

    if p.require_ma_alignment:
        g2 = ind.ma_aligned_bull and ind.close > ind.sma20
        gates.append(GateStatus(
            "2관문 · 추세 정배열", g2,
            f"MA200 {_won(ind.sma200)} < MA60 {_won(ind.sma60)} < MA20 {_won(ind.sma20)} "
            f"{'정배열' if ind.ma_aligned_bull else '아님'} · "
            f"가격 {'>' if ind.close > ind.sma20 else '≤'} MA20",
        ))

    if p.require_pullback:
        pb = detect_pullback(state.frame)
        gates.append(GateStatus("3관문 · 눌림목 반등", pb.triggered, pb.reason))

    if p.require_rsi:
        ok = ind.rsi < p.rsi_overbought
        gates.append(GateStatus(
            "RSI · 과매수 회피", ok,
            f"RSI {ind.rsi:.0f} {'<' if ok else '≥'} 기준 {p.rsi_overbought:.0f}",
        ))

    if p.require_macd:
        gates.append(GateStatus(
            "MACD · 상승 모멘텀", ind.macd_bullish,
            f"MACD {_won(ind.macd)} {'>' if ind.macd_bullish else '≤'} 시그널 {_won(ind.macd_signal)}",
        ))

    if p.require_volume:
        gates.append(GateStatus(
            "거래량 · 평균 이상", ind.volume_above_avg,
            f"거래량 {ind.volume:,.1f} vs 20봉평균 {ind.volume_avg20:,.1f}",
        ))

    return gates


def _exit_gates(position: Position, ind: Indicators) -> list[GateStatus]:
    price = ind.close
    pnl = position.unrealized_pnl_pct(price)
    r = position.r_multiple(price)
    return [
        GateStatus(
            "하드스탑 -3%", pnl <= -0.03,
            f"손익률 {pnl:+.2%} (기준 -3%)",
        ),
        GateStatus(
            "MA60/구름 손절", price < ind.sma60 or price < ind.cloud_top,
            f"가격 {_won(price)} vs MA60 {_won(ind.sma60)} / 구름상단 {_won(ind.cloud_top)}",
        ),
        GateStatus(
            "2R 부분익절", (not position.partial_taken) and r >= 2.0,
            f"현재 {r:.2f}R (부분익절 {'완료' if position.partial_taken else '대기'})",
        ),
        GateStatus(
            "3R/MA20 전량익절", r >= 3.0 or price < ind.sma20,
            f"현재 {r:.2f}R · 가격 {'<' if price < ind.sma20 else '≥'} MA20 {_won(ind.sma20)}",
        ),
    ]
