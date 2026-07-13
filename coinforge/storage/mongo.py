"""MongoRepository — MongoDB 영속화 (CHECKLIST 7.1~7.7).

컬렉션: positions, trade_logs, signal_logs, daily_pnl, system_state.
pymongo 는 선택 의존이므로 이 모듈은 필요할 때만 import 한다.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Optional

from pymongo import ASCENDING, DESCENDING, MongoClient

from ..domain.position import Position
from ..domain.trade import SignalLog, TradeLog


class MongoRepository:
    def __init__(self, uri: str, db_name: str = "coinforge") -> None:
        self._client: MongoClient = MongoClient(uri)
        # URI 에 DB 명이 포함되면 그것을 우선 사용
        default_db = self._client.get_default_database(default=None)
        self._db = default_db if default_db is not None else self._client[db_name]
        self._ensure_indexes()

    def ping(self) -> bool:
        """헬스체크 (7.1)."""
        self._client.admin.command("ping")
        return True

    def _ensure_indexes(self) -> None:
        """인덱스 설계 (7.7)."""
        self._db.positions.create_index([("market", ASCENDING)], unique=True)
        self._db.positions.create_index([("position_id", ASCENDING)])
        self._db.trade_logs.create_index([("timestamp", DESCENDING)])
        self._db.trade_logs.create_index([("position_id", ASCENDING)])
        self._db.signal_logs.create_index([("timestamp", DESCENDING)])
        self._db.daily_pnl.create_index([("day", ASCENDING)], unique=True)
        self._db.system_state.create_index([("key", ASCENDING)], unique=True)

    # --- 포지션 ---------------------------------------------------------------
    def get_open_position(self, market: str) -> Optional[Position]:
        doc = self._db.positions.find_one({"market": market})
        return Position.from_dict(doc) if doc else None

    def save_position(self, position: Position) -> None:
        self._db.positions.replace_one(
            {"market": position.market}, position.to_dict(), upsert=True
        )

    def close_position(self, position_id: str) -> None:
        self._db.positions.delete_one({"position_id": position_id})

    # --- 거래·신호 로그 -------------------------------------------------------
    def append_trade_log(self, log: TradeLog) -> None:
        self._db.trade_logs.insert_one(log.to_dict())

    def list_trade_logs(self, limit: int = 100) -> list[TradeLog]:
        docs = self._db.trade_logs.find().sort("timestamp", DESCENDING).limit(limit)
        out = []
        for d in docs:
            d.pop("_id", None)
            out.append(_trade_from_dict(d))
        return list(reversed(out))

    def append_signal_log(self, log: SignalLog) -> None:
        self._db.signal_logs.insert_one(log.to_dict())

    # --- 일일 PnL -------------------------------------------------------------
    def add_realized_pnl(self, day: date, pnl_krw: float) -> None:
        self._db.daily_pnl.update_one(
            {"day": day.isoformat()},
            {"$inc": {"net_pnl_krw": pnl_krw}, "$set": {"updated_at": _now()}},
            upsert=True,
        )

    def get_daily_loss(self, day: date) -> float:
        doc = self._db.daily_pnl.find_one({"day": day.isoformat()})
        net = float(doc["net_pnl_krw"]) if doc else 0.0
        return -net if net < 0 else 0.0

    # --- 시스템 상태 ----------------------------------------------------------
    def get_state(self, key: str) -> Optional[str]:
        doc = self._db.system_state.find_one({"key": key})
        return doc["value"] if doc else None

    def set_state(self, key: str, value: str) -> None:
        self._db.system_state.update_one(
            {"key": key}, {"$set": {"value": value, "updated_at": _now()}}, upsert=True
        )


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _trade_from_dict(d: dict) -> TradeLog:
    from ..domain.trade import TradeType

    return TradeLog(
        trade_type=TradeType(d["trade_type"]),
        market=d["market"],
        price=d["price"],
        quantity=d["quantity"],
        reason=d["reason"],
        position_id=d.get("position_id", ""),
        stop_price=d.get("stop_price"),
        target_2r=d.get("target_2r"),
        target_3r=d.get("target_3r"),
        pnl_pct=d.get("pnl_pct"),
        pnl_krw=d.get("pnl_krw"),
        mode=d.get("mode", "paper"),
        timestamp=datetime.fromisoformat(d["timestamp"]),
    )
