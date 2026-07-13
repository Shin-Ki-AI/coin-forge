"""cmd/trader — 4H 메인 루프 엔트리포인트 (CHECKLIST 9.8).

paper/live 모드로 4시간마다 사이클을 실행한다. --once 로 1회만 실행 가능.
"""

from __future__ import annotations

import argparse
import logging
import signal

from ..config import load_config
from ..engine.scheduler import FourHourScheduler
from ..factory import build_orchestrator


def main() -> None:
    parser = argparse.ArgumentParser(description="Coin Forge 트레이더 (4H 루프)")
    parser.add_argument("--once", action="store_true", help="한 사이클만 실행하고 종료")
    parser.add_argument("--buffer", type=int, default=None, help="봉 마감 후 대기 초 (기본: 설정값)")
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args()

    logging.basicConfig(
        level=args.log_level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    log = logging.getLogger("coinforge.trader")

    config = load_config()
    log.info("모드: %s · 마켓: %s · 캔들: %d봉", config.trading_mode.value, config.market, config.candle_count)
    orch = build_orchestrator(config)

    if args.once:
        result = orch.run_cycle()
        log.info("사이클 결과: %s — %s", result.action, result.reason)
        return

    buffer = args.buffer if args.buffer is not None else config.scheduler_buffer_seconds
    scheduler = FourHourScheduler(
        callback=lambda: _run_and_log(orch, log),
        buffer_seconds=buffer,
    )

    def _shutdown(signum, frame):  # noqa: ANN001
        log.info("종료 신호 수신 — graceful shutdown")
        scheduler.stop()

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)
    scheduler.run_forever()


def _run_and_log(orch, log) -> None:
    result = orch.run_cycle()
    log.info("사이클 결과: %s — %s", result.action, result.reason)


if __name__ == "__main__":
    main()
