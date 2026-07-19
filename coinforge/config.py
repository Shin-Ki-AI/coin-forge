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

    # --- 비중조절 (#3) ---
    # 사이징 방식: risk(1% 룰) | fixed(고정 비율)
    sizing_mode: str = Field(default=constants.SIZING_MODE_RISK, alias="SIZING_MODE")
    # 1회 주문금액 상한(자본 대비). 100% 올인 방지. 1.0 이면 상한 없음.
    max_position_pct: float = Field(default=constants.MAX_POSITION_PCT, alias="MAX_POSITION_PCT")
    # fixed 모드에서 자본 대비 주문금액 비율.
    fixed_position_pct: float = Field(
        default=constants.FIXED_POSITION_PCT, alias="FIXED_POSITION_PCT"
    )

    # --- 모의투자 (#1) ---
    # 모의계좌 상태 JSON 경로 (재시작해도 누적 유지).
    paper_state_path: str = Field(default="paper_state.json", alias="PAPER_STATE_PATH")

    # --- 전략 튜닝 (#2 + 보조기법) — 실거래/모의투자에 적용 ---
    ma_short: int = Field(default=constants.MA_SHORT, alias="MA_SHORT")
    ma_mid: int = Field(default=constants.MA_MID, alias="MA_MID")
    ma_long: int = Field(default=constants.MA_LONG, alias="MA_LONG")
    partial_take_r: float = Field(default=constants.PARTIAL_TAKE_R, alias="PARTIAL_TAKE_R")
    full_take_r: float = Field(default=constants.FULL_TAKE_R, alias="FULL_TAKE_R")
    require_cloud: bool = Field(default=True, alias="REQUIRE_CLOUD")
    require_ma_alignment: bool = Field(default=True, alias="REQUIRE_MA_ALIGNMENT")
    require_pullback: bool = Field(default=True, alias="REQUIRE_PULLBACK")
    require_volume: bool = Field(default=False, alias="REQUIRE_VOLUME")
    require_rsi: bool = Field(default=False, alias="REQUIRE_RSI")
    rsi_period: int = Field(default=constants.RSI_PERIOD, alias="RSI_PERIOD")
    rsi_overbought: float = Field(default=constants.RSI_OVERBOUGHT, alias="RSI_OVERBOUGHT")
    require_macd: bool = Field(default=False, alias="REQUIRE_MACD")
    macd_fast: int = Field(default=constants.MACD_FAST, alias="MACD_FAST")
    macd_slow: int = Field(default=constants.MACD_SLOW, alias="MACD_SLOW")
    macd_signal_period: int = Field(default=constants.MACD_SIGNAL, alias="MACD_SIGNAL")

    def strategy_params(self):
        """설정값으로 StrategyParams 를 만든다 (실거래/모의투자/신호진단 공통)."""
        from .strategy.params import StrategyParams

        return StrategyParams(
            ma_short=self.ma_short, ma_mid=self.ma_mid, ma_long=self.ma_long,
            partial_take_r=self.partial_take_r, full_take_r=self.full_take_r,
            hard_stop_pct=self.hard_stop_pct,
            require_cloud=self.require_cloud, require_ma_alignment=self.require_ma_alignment,
            require_pullback=self.require_pullback, require_volume=self.require_volume,
            require_rsi=self.require_rsi, rsi_period=self.rsi_period,
            rsi_overbought=self.rsi_overbought,
            require_macd=self.require_macd, macd_fast=self.macd_fast,
            macd_slow=self.macd_slow, macd_signal_period=self.macd_signal_period,
        )

    @property
    def is_live(self) -> bool:
        return self.trading_mode == TradingMode.LIVE


def load_config() -> Config:
    """설정을 로드한다. (환경변수 + .env + 기본값)"""
    return Config()
