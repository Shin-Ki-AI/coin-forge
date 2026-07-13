"""스케줄러 경계 계산 테스트 (CHECKLIST 9.1, D5)."""

from __future__ import annotations

from datetime import datetime, timezone

from coinforge.engine.scheduler import next_boundary


def test_next_boundary_mid_period():
    now = datetime(2026, 1, 1, 5, 30, tzinfo=timezone.utc)
    # 4H 경계: 00,04,08,... → 5:30 다음은 08:00
    assert next_boundary(now) == datetime(2026, 1, 1, 8, 0, tzinfo=timezone.utc)


def test_next_boundary_exact_boundary_advances():
    now = datetime(2026, 1, 1, 8, 0, tzinfo=timezone.utc)
    # 정확히 경계면 다음 경계로
    assert next_boundary(now) == datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)


def test_next_boundary_crosses_midnight():
    now = datetime(2026, 1, 1, 22, 15, tzinfo=timezone.utc)
    assert next_boundary(now) == datetime(2026, 1, 2, 0, 0, tzinfo=timezone.utc)
