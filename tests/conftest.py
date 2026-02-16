"""Shared fixtures for the test suite."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
import pytest
from httpx import ASGITransport, AsyncClient

from app.db import get_session
from app.main import app


# ---------------------------------------------------------------------------
# Fake DB session (no real Postgres needed)
# ---------------------------------------------------------------------------

class FakeSession:
    """Minimal stand-in for AsyncSession used in endpoint tests."""

    def __init__(self, rows: list[dict[str, Any]] | None = None):
        self._rows = rows or []

    async def execute(self, stmt, params=None):
        return FakeResult(self._rows)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass


class FakeResult:
    def __init__(self, rows: list[dict[str, Any]]):
        self._rows = rows
        self._keys = list(rows[0].keys()) if rows else []

    def keys(self):
        return self._keys

    def fetchall(self):
        return [tuple(r[k] for k in self._keys) for r in self._rows]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def fake_session():
    """Return a FakeSession with no rows (override _rows in tests if needed)."""
    return FakeSession()


@pytest.fixture()
def override_session(fake_session):
    """Override the FastAPI dependency so no real DB is needed."""
    async def _override():
        yield fake_session

    app.dependency_overrides[get_session] = _override
    yield fake_session
    app.dependency_overrides.clear()


@pytest.fixture()
async def client(override_session):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


def make_row(
    record_type: str,
    value: float,
    ts: datetime | None = None,
    row_id: int = 1,
) -> dict[str, Any]:
    """Helper to build a fake health_records row dict."""
    if ts is None:
        ts = datetime(2026, 2, 15, 12, 0, tzinfo=timezone.utc)
    return {
        "id": row_id,
        "record_type": record_type,
        "start_date": ts,
        "end_date": ts,
        "data": {"value": value},
    }
