"""Orchestrator — 한 4H 사이클의 데이터→지표→분기→주문→기록→알림 (CHECKLIST 9).

PLAN.md 실행 플로우:
  캔들 조회 → 지표 계산 → 거래 허용? → [포지션] 청산 평가 → [무포지션] 방어·진입 평가
  → 주문 → 로그 → 알림
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Optional

from ..config import Config
from ..domain.indicators import Indicators
from ..domain.position import ExitAction, Position
from ..domain.trade import SignalLog, TradeLog, TradeType
from ..indicators.engine import IndicatorEngine, InsufficientCandlesError
from ..notify.event import TradeEvent
from ..risk.manager import RiskManager
from ..strategy import build_market_state, evaluate_defense, evaluate_entry, evaluate_exit

log = logging.getLogger(__name__)


@dataclass
class CycleResult:
    action: str          # "entry" | "exit" | "partial_exit" | "blocked" | "hold" | "halt" | "error"
    reason: str
    price: float = 0.0
    quantity: float = 0.0


class Orchestrator:
    def __init__(
        self,
        *,
        config: Config,
        candle_provider,
        exchange,
        repository,
        notifier,
        risk_manager: Optional[RiskManager] = None,
        indicator_engine: Optional[IndicatorEngine] = None,
    ) -> None:
        self.config = config
        self.candles = candle_provider
        self.exchange = exchange
        self.repo = repository
        self.notifier = notifier
        self.risk = risk_manager or RiskManager(config)
        self.engine = indicator_engine or IndicatorEngine(min_candles=config.candle_count)

    # --- 메인 사이클 ----------------------------------------------------------
    def run_cycle(self, now: Optional[datetime] = None) -> CycleResult:
        now = now or datetime.now(timezone.utc)
        market = self.config.market
        try:
            candles = self.candles.get_candles(self.config.candle_count)
            state = build_market_state(candles, self.engine)
        except (InsufficientCandlesError, RuntimeError) as exc:
            return self._error(f"데이터/지표 오류: {exc}")

        ind = state.indicators
        price = ind.close
        # Mock 거래소는 평가에 현재가가 필요
        if hasattr(self.exchange, "set_price"):
            self.exchange.set_price(price)

        position = self.repo.get_open_position(market)

        if position is not None:
            return self._handle_position(position, ind, now)
        return self._handle_no_position(state, ind, now)

    # --- 포지션 보유 분기 (9.3) -----------------------------------------------
    def _handle_position(
        self, position: Position, ind: Indicators, now: datetime
    ) -> CycleResult:
        res = evaluate_exit(position, ind)
        if res.action == ExitAction.HOLD:
            self._signal("hold", res.reason, ind.close)
            return CycleResult("hold", res.reason, ind.close)

        price = ind.close
        order = self.exchange.sell_market(self.config.market, price, res.quantity)
        if not order.ok:
            return self._error(f"매도 주문 실패: {order.reason}")

        realized_krw = (order.price - position.entry_price) * order.quantity - order.fee
        self.repo.add_realized_pnl(now.date(), realized_krw)

        if res.action == ExitAction.PARTIAL_EXIT:
            position.quantity -= order.quantity
            position.partial_taken = True
            self.repo.save_position(position)
            self._log_trade(
                TradeType.PARTIAL_EXIT, order.price, order.quantity, res.reason,
                position, pnl_pct=res.pnl_pct, pnl_krw=realized_krw,
            )
            self._notify("partial_exit", order.price, order.quantity, res.reason,
                         position, pnl=res.pnl_pct)
            return CycleResult("partial_exit", res.reason, order.price, order.quantity)

        # 전량 청산
        self.repo.close_position(position.position_id)
        self._log_trade(
            TradeType.EXIT, order.price, order.quantity, res.reason,
            position, pnl_pct=res.pnl_pct, pnl_krw=realized_krw,
        )
        self._notify("exit", order.price, order.quantity, res.reason,
                     position, pnl=res.pnl_pct)
        return CycleResult("exit", res.reason, order.price, order.quantity)

    # --- 무포지션 분기 (9.4) --------------------------------------------------
    def _handle_no_position(self, state, ind: Indicators, now: datetime) -> CycleResult:
        balance = self.exchange.get_balance()
        equity = balance.krw + balance.btc * ind.close

        halt = self.risk.check_trading_allowed(
            has_open_position=False,
            daily_loss_krw=self.repo.get_daily_loss(now.date()),
            equity_krw=equity if equity > 0 else self.config.total_equity_krw,
        )
        if halt.halted:
            self._signal("halt", halt.reason, ind.close)
            self.notifier.send(TradeEvent(
                type="circuit_breaker", market=self.config.market,
                price=ind.close, reason=halt.reason,
            ))
            return CycleResult("halt", halt.reason, ind.close)

        defense = evaluate_defense(ind, None)
        if defense.blocked:
            self._signal("blocked", defense.reason, ind.close)
            return CycleResult("blocked", defense.reason, ind.close)

        entry = evaluate_entry(state)
        if not entry.signal:
            self._signal("no_signal", entry.reason, ind.close)
            return CycleResult("hold", entry.reason, ind.close)

        # 사이징 → 주문
        equity_for_sizing = equity if equity > 0 else self.config.total_equity_krw
        sizing = self.risk.compute_sizing(
            entry_price=ind.close, ind=ind,
            equity_krw=equity_for_sizing, available_krw=balance.krw,
        )
        if not sizing.ok:
            self._signal("blocked", f"사이징 실패: {sizing.reason}", ind.close)
            return CycleResult("blocked", sizing.reason, ind.close)

        order = self.exchange.buy_market(self.config.market, ind.close, sizing.quantity)
        if not order.ok:
            return self._error(f"매수 주문 실패: {order.reason}")

        position = Position(
            market=self.config.market,
            entry_price=order.price,
            quantity=order.quantity,
            stop_price=sizing.stop_price,
            entry_reason=entry.reason,
            initial_quantity=order.quantity,
            opened_at=now,
        )
        self.repo.save_position(position)
        self._log_trade(
            TradeType.ENTRY, order.price, order.quantity, entry.reason, position,
        )
        self._notify("entry", order.price, order.quantity, entry.reason, position)
        return CycleResult("entry", entry.reason, order.price, order.quantity)

    # --- 헬퍼 -----------------------------------------------------------------
    def _log_trade(
        self, ttype: TradeType, price: float, qty: float, reason: str,
        position: Position, pnl_pct=None, pnl_krw=None,
    ) -> None:
        self.repo.append_trade_log(TradeLog(
            trade_type=ttype, market=self.config.market, price=price, quantity=qty,
            reason=reason, position_id=position.position_id,
            stop_price=position.stop_price, target_2r=position.target_2r,
            target_3r=position.target_3r, pnl_pct=pnl_pct, pnl_krw=pnl_krw,
            mode=self.config.trading_mode.value,
        ))

    def _notify(self, etype: str, price: float, qty: float, reason: str,
                position: Position, pnl=None) -> None:
        self.notifier.send(TradeEvent(
            type=etype, market=self.config.market, price=price, quantity=qty,
            stop_price=position.stop_price, target_2r=position.target_2r,
            target_3r=position.target_3r, pnl_percent=pnl, reason=reason,
        ))

    def _signal(self, action: str, reason: str, price: float) -> None:
        self.repo.append_signal_log(SignalLog(
            market=self.config.market, action=action, reason=reason, price=price,
        ))

    def _error(self, msg: str) -> CycleResult:
        log.error(msg)
        self.repo.append_signal_log(SignalLog(
            market=self.config.market, action="error", reason=msg, price=0.0,
        ))
        self.notifier.send(TradeEvent(
            type="error", market=self.config.market, reason=msg,
        ))
        return CycleResult("error", msg)
