"""UpbitRestCandleProvider — 업비트 REST 4H 캔들 공급자 (실용 기본값).

문서상 D4 결정은 UpbitBridge WebSocket이지만, 외부 브릿지 없이도 즉시 동작하도록
업비트 공개 REST(/v1/candles/minutes/240)에서 240봉을 직접 수집한다.
CandleProvider 인터페이스를 만족하므로 엔진에 그대로 주입 가능.

주의: REST의 최신 캔들은 "형성 중(미완성)" 봉이다. 신호는 완성된 봉으로만 내야
백테스트(_SlidingProvider는 완성봉만 노출)와 일치하므로, 아직 마감되지 않은 봉을
타임스탬프 기준으로 걸러낸다(#4).
"""

from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from typing import Callable

import requests

from .. import constants
from ..domain.candle import Candle

_UNIT = constants.TIMEFRAME_MINUTES  # 240분 = 4H
_URL = f"{constants.UPBIT_REST_BASE}/v1/candles/minutes/{_UNIT}"
_MAX_PER_CALL = 200


def drop_forming(
    candles: list[Candle],
    now: datetime,
    period_minutes: int = constants.TIMEFRAME_MINUTES,
) -> list[Candle]:
    """마감된 봉만 반환한다. 봉 [시작, 시작+period) 가 now 이전에 끝난 것만 완성봉."""
    horizon = timedelta(minutes=period_minutes)
    return [c for c in candles if c.datetime + horizon <= now]


class UpbitRestCandleProvider:
    """업비트 REST에서 최근 4H 캔들을 페이지네이션으로 수집."""

    def __init__(
        self,
        market: str = constants.MARKET,
        session: requests.Session | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.market = market
        self._session = session or requests.Session()
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def get_candles(self, count: int) -> list[Candle]:
        # 형성 중 봉 1개를 버릴 여유로 count+1 개를 수집.
        target = count + 1
        collected: list[dict] = []
        to_param: str | None = None

        while len(collected) < target:
            remaining = target - len(collected)
            size = min(_MAX_PER_CALL, remaining)
            params = {"market": self.market, "count": size}
            if to_param:
                params["to"] = to_param

            resp = self._session.get(_URL, params=params, timeout=10)
            resp.raise_for_status()
            batch = resp.json()
            if not batch:
                break

            collected.extend(batch)
            # 업비트는 최신→과거 순. 가장 과거 봉 시각을 다음 to로.
            oldest = batch[-1]["candle_date_time_utc"]
            to_param = oldest  # ISO8601, 업비트가 해당 시각 이전을 반환
            time.sleep(1.0 / constants.UPBIT_RATE_LIMIT_PER_SEC)

        candles = [_to_candle(row) for row in collected]
        candles.sort(key=lambda c: c.datetime)
        candles = drop_forming(candles, self._clock())  # 미완성 봉 제거(#4)

        if len(candles) < count:
            raise RuntimeError(
                f"업비트 완성봉 부족: {len(candles)}개 확보, {count}개 요청"
            )
        return candles[-count:]


def _to_candle(row: dict) -> Candle:
    dt = datetime.fromisoformat(row["candle_date_time_utc"]).replace(tzinfo=timezone.utc)
    return Candle(
        datetime=dt,
        open=float(row["opening_price"]),
        high=float(row["high_price"]),
        low=float(row["low_price"]),
        close=float(row["trade_price"]),
        volume=float(row["candle_acc_trade_volume"]),
    )
