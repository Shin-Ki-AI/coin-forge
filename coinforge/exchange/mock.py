"""MockExchange — paper 트레이딩·테스트용 인메모리 거래소 (CHECKLIST 4.9).

실주문 없이 KRW/BTC 잔고를 시뮬레이션한다. 현재가는 외부에서 set_price 로 주입.
시장가 체결은 slippage_bp 만큼 불리하게(매수↑·매도↓) 밀려 live 실체결과 정합을 맞춘다.
"""

from __future__ import annotations

from uuid import uuid4

from .. import constants
from .base import Balance, OrderResult, OrderSide

DEFAULT_FEE_RATE = 0.0005  # 업비트 원화마켓 수수료(참고치)


class MockExchange:
    """인메모리 거래소. 백테스트·paper 모드에서 주입."""

    def __init__(
        self,
        krw: float = 1_000_000.0,
        btc: float = 0.0,
        fee_rate: float = DEFAULT_FEE_RATE,
        market: str = constants.MARKET,
        slippage_bp: float = 0.0,
    ) -> None:
        self._krw = krw
        self._btc = btc
        self.fee_rate = fee_rate
        self.market = market
        self.slippage_bp = slippage_bp
        self._price = 0.0

    def set_price(self, price: float) -> None:
        self._price = price

    def get_price(self, market: str) -> float:
        return self._price

    def get_balance(self) -> Balance:
        return Balance(krw=self._krw, btc=self._btc)

    def _fill_price(self, price: float, side: OrderSide) -> float:
        """요청가에 슬리피지를 적용한 체결가. 매수는 위로, 매도는 아래로 불리하게."""
        adj = self.slippage_bp / 10_000.0
        if side is OrderSide.BUY:
            return price * (1.0 + adj)
        return price * (1.0 - adj)

    def buy_market(self, market: str, price: float, quantity: float) -> OrderResult:
        fill = self._fill_price(price, OrderSide.BUY)
        notional = fill * quantity
        fee = notional * self.fee_rate
        total = notional + fee
        if total > self._krw + 1e-6:
            return OrderResult(
                ok=False, side=OrderSide.BUY, market=market, price=fill,
                quantity=0.0, reason=f"잔고 부족 (필요 {total:,.0f} > 보유 {self._krw:,.0f})",
            )
        self._krw -= total
        self._btc += quantity
        return OrderResult(
            ok=True, side=OrderSide.BUY, market=market, price=fill,
            quantity=quantity, fee=fee, order_id=uuid4().hex, reason="mock 매수 체결",
        )

    def sell_market(self, market: str, price: float, quantity: float) -> OrderResult:
        qty = min(quantity, self._btc)
        if qty <= 0:
            return OrderResult(
                ok=False, side=OrderSide.SELL, market=market, price=price,
                quantity=0.0, reason="매도 가능 BTC 없음",
            )
        fill = self._fill_price(price, OrderSide.SELL)
        notional = fill * qty
        fee = notional * self.fee_rate
        self._btc -= qty
        self._krw += notional - fee
        return OrderResult(
            ok=True, side=OrderSide.SELL, market=market, price=fill,
            quantity=qty, fee=fee, order_id=uuid4().hex, reason="mock 매도 체결",
        )

    @property
    def equity_krw(self) -> float:
        """평가 자산 = KRW + BTC*현재가."""
        return self._krw + self._btc * self._price
