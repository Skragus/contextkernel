"""Endpoint tests — FastAPI TestClient via httpx."""

from __future__ import annotations

from unittest.mock import patch

import pytest


class TestCardsEndpoint:
    @pytest.mark.asyncio
    async def test_unknown_card_type_404(self, client):
        resp = await client.get("/kernel/cards/nonexistent?from=2026-02-15&to=2026-02-15")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_missing_dates_422(self, client):
        resp = await client.get("/kernel/cards/daily_summary")
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_daily_summary_200(self, client):
        with patch("app.kernel.builders.connector.fetch_records", return_value=[]):
            resp = await client.get("/kernel/cards/daily_summary?from=2026-02-15&to=2026-02-15")
        assert resp.status_code == 200
        body = resp.json()
        assert body["schema_version"] == "v0"
        assert body["card_type"] == "daily_summary"

    @pytest.mark.asyncio
    async def test_weekly_overview_200(self, client):
        with patch("app.kernel.builders.connector.fetch_records", return_value=[]):
            resp = await client.get("/kernel/cards/weekly_overview?from=2026-02-09&to=2026-02-15")
        assert resp.status_code == 200
        assert resp.json()["card_type"] == "weekly_overview"

    @pytest.mark.asyncio
    async def test_monthly_overview_200(self, client):
        with patch("app.kernel.builders.connector.fetch_records", return_value=[]):
            resp = await client.get("/kernel/cards/monthly_overview?from=2026-02-01&to=2026-02-28")
        assert resp.status_code == 200
        assert resp.json()["card_type"] == "monthly_overview"


class TestPresetsEndpoints:
    @pytest.mark.asyncio
    async def test_list_presets(self, client):
        resp = await client.get("/kernel/presets")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) == 3
        ids = {p["id"] for p in data}
        assert ids == {"daily_brief", "weekly_health", "monthly_overview"}

    @pytest.mark.asyncio
    async def test_preset_detail(self, client):
        resp = await client.get("/kernel/presets/daily_brief")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "daily_brief"
        assert "daily_summary" in data["card_types"]

    @pytest.mark.asyncio
    async def test_preset_not_found(self, client):
        resp = await client.get("/kernel/presets/nope")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_preset_run(self, client):
        with patch("app.kernel.builders.connector.fetch_records", return_value=[]):
            resp = await client.get(
                "/kernel/presets/daily_brief/run?from=2026-02-15&to=2026-02-15"
            )
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["card_type"] == "daily_summary"

    @pytest.mark.asyncio
    async def test_preset_run_not_found(self, client):
        resp = await client.get("/kernel/presets/nope/run?from=2026-02-15&to=2026-02-15")
        assert resp.status_code == 404


class TestHealthEndpoint:
    @pytest.mark.asyncio
    async def test_health(self, client):
        resp = await client.get("/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}
