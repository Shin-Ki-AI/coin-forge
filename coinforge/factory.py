"""컴포넌트 조립 — Config 로 거래소·캔들·저장소·알림·오케스트레이터를 주입한다.

- 캔들: 항상 실시장 데이터 (업비트 REST 4H). paper/live 공통.
- 거래소: paper → MockExchange, live → UpbitExchange.
- 저장소: MONGO 연결 성공 시 MongoRepository, 실패 시 InMemory 로 폴백.
- 알림: Telegram + PushOver (미설정 시 자동 무시).
"""

from __future__ import annotations

import logging

from .config import Config
from .engine.orchestrator import Orchestrator
from .exchange.mock import MockExchange
from .notify.mock import MockNotifier
from .notify.multi import MultiNotifier
from .notify.pushover import PushOverNotifier
from .notify.telegram import TelegramNotifier

log = logging.getLogger(__name__)


def build_candle_provider(config: Config):
    from .bridge.upbit_rest import UpbitRestCandleProvider

    return UpbitRestCandleProvider(market=config.market)


def build_exchange(config: Config):
    if config.is_live:
        from .exchange.upbit import UpbitExchange

        return UpbitExchange(
            access_key=config.upbit_access_key,
            secret_key=config.upbit_secret_key,
            market=config.market,
            order_type=config.order_type,
        )
    return MockExchange(
        krw=config.total_equity_krw, btc=0.0, market=config.market,
        slippage_bp=config.slippage_bp,
    )


def build_repository(config: Config):
    try:
        from .storage.mongo import MongoRepository

        repo = MongoRepository(config.mongo_uri)
        repo.ping()
        log.info("MongoDB 연결 성공")
        return repo
    except Exception as exc:  # noqa: BLE001 — 폴백 허용
        log.warning("MongoDB 연결 실패 → 인메모리 저장소로 폴백: %s", exc)
        from .storage.memory import InMemoryRepository

        return InMemoryRepository()


def build_notifier(config: Config):
    notifiers = []
    if config.telegram_bot_token and config.telegram_chat_id:
        notifiers.append(TelegramNotifier(config.telegram_bot_token, config.telegram_chat_id))
    if config.pushover_user_key and config.pushover_api_token:
        notifiers.append(PushOverNotifier(config.pushover_user_key, config.pushover_api_token))
    if not notifiers:
        log.warning("알림 채널 미설정 — MockNotifier 사용 (전송 없음)")
        return MockNotifier()
    return MultiNotifier(notifiers)


def build_orchestrator(config: Config) -> Orchestrator:
    return Orchestrator(
        config=config,
        candle_provider=build_candle_provider(config),
        exchange=build_exchange(config),
        repository=build_repository(config),
        notifier=build_notifier(config),
    )
