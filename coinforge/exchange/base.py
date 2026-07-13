"""Exchange 인터페이스 (CHECKLIST 4.9).

주문·잔고·현재가 조회를 추상화. 엔진은 이 인터페이스에만 의존하고,
paper 모드는 MockExchange, live 모드는 UpbitExchange를 주입한다.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Protocol, runtime_checkable


class OrderSide(str, Enum):
    BUY = "buy"
    SELL = "sell"


@dataclass
class Balance:
    krw: float          # 주문 가능 KRW
    btc: float          # 보유 BTC
    krw_locked: float = 0.0
    btc_locked: float = 0.0


@dataclass
class OrderResult:
    ok: bool
    side: OrderSide
    market: str
    price: float         # 평균 체결가
    quantity: float      # 체결 수량 (BTC)
    fee: float = 0.0
    order_id: str = ""
    reason: str = ""


@runtime_checkable
class Exchange(Protocol):
    """거래소 주문·잔고 게이트웨이."""

    def get_price(self, market: str) -> float:
        """현재가 조회."""
        ...

    def get_balance(self) -> Balance:
        """KRW·BTC 잔고 조회."""
        ...

    def buy_market(self, market: str, price: float, quantity: float) -> OrderResult:
        """시장가 매수 (quantity BTC 상당)."""
        ...

    def sell_market(self, market: str, price: float, quantity: float) -> OrderResult:
        """시장가 매도 (quantity BTC)."""
        ...
