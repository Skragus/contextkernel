"""Hardcoded preset definitions — configuration only."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class Preset:
    id: str
    label: str
    description: str
    card_types: list[str] = field(default_factory=list)


PRESETS: dict[str, Preset] = {
    "daily_brief": Preset(
        id="daily_brief",
        label="Daily Brief",
        description="Single-day summary card.",
        card_types=["daily_summary"],
    ),
    "weekly_health": Preset(
        id="weekly_health",
        label="Weekly Health",
        description="7-day overview card.",
        card_types=["weekly_overview"],
    ),
    "monthly_overview": Preset(
        id="monthly_overview",
        label="Monthly Overview",
        description="Full-month overview card.",
        card_types=["monthly_overview"],
    ),
}


def list_presets() -> list[Preset]:
    return list(PRESETS.values())


def get_preset(preset_id: str) -> Preset | None:
    return PRESETS.get(preset_id)
