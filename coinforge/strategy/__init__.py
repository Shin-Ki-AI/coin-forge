"""트레이딩 전략 엔진 — 진입·방어·청산 평가."""

from .context import MarketState, build_market_state
from .defense import DefenseResult, evaluate_defense
from .diagnostics import GateStatus, SignalDiagnostics, evaluate_signal
from .entry import EntryResult, evaluate_entry
from .exit import ExitResult, evaluate_exit
from .pullback import PullbackResult, detect_pullback

__all__ = [
    "MarketState",
    "build_market_state",
    "evaluate_entry",
    "EntryResult",
    "evaluate_defense",
    "DefenseResult",
    "evaluate_exit",
    "ExitResult",
    "detect_pullback",
    "PullbackResult",
    "evaluate_signal",
    "SignalDiagnostics",
    "GateStatus",
]
