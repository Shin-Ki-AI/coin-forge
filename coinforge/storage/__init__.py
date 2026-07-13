"""영속화 — Repository 인터페이스, 인메모리·MongoDB 구현."""

from .base import Repository
from .memory import InMemoryRepository

__all__ = ["Repository", "InMemoryRepository"]


def mongo_repository(*args, **kwargs):
    """MongoRepository 지연 로딩 (pymongo 선택 의존)."""
    from .mongo import MongoRepository

    return MongoRepository(*args, **kwargs)
