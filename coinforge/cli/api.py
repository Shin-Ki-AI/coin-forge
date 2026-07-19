"""cmd/api — 대시보드 API 서버 엔트리포인트 (CHECKLIST 11.1.6).

모의투자(#1)를 실시간으로 전진시키기 위해, 서버로 뜰 때 4H 스케줄러를 데몬
스레드로 함께 돌린다(--no-paper-autorun 으로 끌 수 있음). 대시보드의 "한 사이클
실행" 버튼으로 수동 전진도 가능.
"""

from __future__ import annotations

import argparse
import logging
import threading

log = logging.getLogger("coinforge.api")


def main() -> None:
    parser = argparse.ArgumentParser(description="Coin Forge API 서버")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--no-paper-autorun", action="store_true",
                        help="모의투자 4H 자동 전진 비활성화 (수동 실행만)")
    args = parser.parse_args()

    logging.basicConfig(level="INFO", format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    import uvicorn

    from ..api.app import create_app
    from ..config import load_config
    from ..engine.scheduler import FourHourScheduler

    config = load_config()
    app = create_app(config)

    if not args.no_paper_autorun:
        engine = app.state.paper_engine
        scheduler = FourHourScheduler(
            callback=lambda: _safe_step(engine),
            buffer_seconds=config.scheduler_buffer_seconds,
        )
        threading.Thread(target=scheduler.run_forever, daemon=True).start()
        log.info("모의투자 자동 전진 활성화 (4H 봉 마감마다 전진)")

    uvicorn.run(app, host=args.host, port=args.port)


def _safe_step(engine) -> None:
    try:
        result = engine.step()
        log.info("모의투자 사이클: %s — %s", result.action, result.reason)
    except Exception:  # noqa: BLE001 — 스케줄러 스레드는 죽지 않아야 함
        log.exception("모의투자 사이클 실패")


if __name__ == "__main__":
    main()
