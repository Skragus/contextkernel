"""Kernel HTTP router — cards & presets."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import get_session
from app.kernel import builders
from app.kernel.models import CardEnvelope
from app.kernel.presets import get_preset, list_presets

router = APIRouter(prefix="/kernel", tags=["kernel"])

# Mapping card_type string → builder callable
CARD_BUILDERS = {
    "daily_summary",
    "weekly_overview",
    "monthly_overview",
}


def _parse_date(value: str, name: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise HTTPException(status_code=422, detail=f"Invalid date for '{name}': {value}")


# ---------------------------------------------------------------------------
# /kernel/cards/{card_type}
# ---------------------------------------------------------------------------


@router.get("/cards/{card_type}", response_model=CardEnvelope)
async def get_card(
    card_type: str,
    session: AsyncSession = Depends(get_session),
    from_date: str = Query(..., alias="from", description="Start date (YYYY-MM-DD)"),
    to_date: str = Query(..., alias="to", description="End date (YYYY-MM-DD)"),
    tz: str = Query(default=None, description="Timezone (e.g. US/Eastern)"),
) -> CardEnvelope:
    if card_type not in CARD_BUILDERS:
        raise HTTPException(status_code=404, detail=f"Unknown card type: {card_type}")

    tz_name = tz or settings.default_tz
    start = _parse_date(from_date, "from")
    _parse_date(to_date, "to")  # validate

    if card_type == "daily_summary":
        return await builders.build_daily_summary(session, start, tz_name)

    if card_type == "weekly_overview":
        return await builders.build_weekly_overview(session, start, tz_name)

    if card_type == "monthly_overview":
        return await builders.build_monthly_overview(session, start.year, start.month, tz_name)

    raise HTTPException(status_code=404, detail=f"Unknown card type: {card_type}")


# ---------------------------------------------------------------------------
# /kernel/presets
# ---------------------------------------------------------------------------


@router.get("/presets")
async def presets_list() -> list[dict]:
    return [
        {"id": p.id, "label": p.label, "description": p.description, "card_types": p.card_types}
        for p in list_presets()
    ]


@router.get("/presets/{preset_id}")
async def preset_detail(preset_id: str) -> dict:
    preset = get_preset(preset_id)
    if preset is None:
        raise HTTPException(status_code=404, detail=f"Unknown preset: {preset_id}")
    return {
        "id": preset.id,
        "label": preset.label,
        "description": preset.description,
        "card_types": preset.card_types,
    }


@router.get("/presets/{preset_id}/run", response_model=list[CardEnvelope])
async def preset_run(
    preset_id: str,
    session: AsyncSession = Depends(get_session),
    from_date: str = Query(..., alias="from", description="Start date (YYYY-MM-DD)"),
    to_date: str = Query(..., alias="to", description="End date (YYYY-MM-DD)"),
    tz: str = Query(default=None, description="Timezone"),
) -> list[CardEnvelope]:
    preset = get_preset(preset_id)
    if preset is None:
        raise HTTPException(status_code=404, detail=f"Unknown preset: {preset_id}")

    tz_name = tz or settings.default_tz
    start = _parse_date(from_date, "from")
    _parse_date(to_date, "to")  # validate

    results: list[CardEnvelope] = []
    for ct in preset.card_types:
        if ct == "daily_summary":
            results.append(await builders.build_daily_summary(session, start, tz_name))
        elif ct == "weekly_overview":
            results.append(await builders.build_weekly_overview(session, start, tz_name))
        elif ct == "monthly_overview":
            results.append(
                await builders.build_monthly_overview(session, start.year, start.month, tz_name)
            )
    return results
