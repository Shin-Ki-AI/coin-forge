"""환경변수 기반 설정 로더 (CHECKLIST 2.5).

.env.example 템플릿의 값을 읽어 타입 안전한 Config 객체로 제공한다.
민감정보(API 키)는 코드/로그에 노출하지 않는다.
"""

from __future__ import annotations

from enum import Enum

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from . import constants


class TradingMode(str, Enum):
    PAPER = "paper"
    LIVE = "live"


class Config(BaseSettings):
    """전 시스템 주입용 설정. 환경변수 → 기본값 순으로 로드."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Upbit (주문·잔고) ---
    upbit_access_key: str = Field(default="", alias="UPBIT_ACCESS_KEY")
    upbit_secret_key: str = Field(default="", alias="UPBIT_SECRET_KEY")

    # --- UpbitBridge (캔들 수집) ---
    upbit_bridge_ws_url: str = Field(
        default="ws://localhost:8080/ws", alias="UPBIT_BRIDGE_WS_URL"
    )
    candle_count: int = Field(default=constants.CANDLE_COUNT, alias="CANDLE_COUNT")

    # --- MongoDB ---
    mongo_uri: str = Field(
        default="mongodb://localhost:27017/coinforge", alias="MONGO_URI"
    )

    # --- Notifications ---
    telegram_bot_token: str = Field(default="", alias="TELEGRAM_BOT_TOKEN")
    telegram_chat_id: str = Field(default="", alias="TELEGRAM_CHAT_ID")
    pushover_user_key: str = Field(default="", alias="PUSHOVER_USER_KEY")
    pushover_api_token: str = Field(default="", alias="PUSHOVER_API_TOKEN")

    # --- Trading ---
    market: str = Field(default=constants.MARKET, alias="MARKET")
    trading_mode: TradingMode = Field(default=TradingMode.PAPER, alias="TRADING_MODE")
    total_equity_krw: float = Field(default=1_000_000, alias="TOTAL_EQUITY_KRW")
    # paper/백테스트 시장가 체결 슬리피지(bp). live 는 실체결가를 쓰므로 무시됨.
    slippage_bp: float = Field(default=constants.BACKTEST_SLIPPAGE_BP, alias="SLIPPAGE_BP")
    # 봉 마감 후 사이클 실행까지 대기 초 (D5). 완성봉 선택은 타임스탬프 기준.
    scheduler_buffer_seconds: int = Field(
        default=constants.SCHEDULER_BUFFER_SECONDS, alias="SCHEDULER_BUFFER_SECONDS"
    )
    # live 주문 유형: market | limit. limit 은 미체결 시 시장가 폴백.
    order_type: str = Field(default=constants.ORDER_TYPE_MARKET, alias="ORDER_TYPE")

    # --- Risk ---
    risk_per_trade_pct: float = Field(
        default=constants.RISK_PER_TRADE_PCT, alias="RISK_PER_TRADE_PCT"
    )
    daily_loss_limit_pct: float = Field(
        default=constants.DAILY_LOSS_LIMIT_PCT, alias="DAILY_LOSS_LIMIT_PCT"
    )
    hard_stop_pct: float = Field(default=constants.HARD_STOP_PCT, alias="HARD_STOP_PCT")

    @property
    def is_live(self) -> bool:
        return self.trading_mode == TradingMode.LIVE


def load_config() -> Config:
    """설정을 로드한다. (환경변수 + .env + 기본값)"""
    return Config()
