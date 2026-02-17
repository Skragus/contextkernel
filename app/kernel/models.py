"""CardEnvelope v0 contract — Pydantic v2 models."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class Granularity(str, Enum):
    daily = "daily"
    weekly = "weekly"
    monthly = "monthly"


class TimeRange(BaseModel):
    start: datetime
    end: datetime
    timezone: str = "UTC"


class Signal(BaseModel):
    name: str
    record_type: str
    value: float | None = None
    unit: str | None = None
    aggregation: str = "avg"
    baseline: float | None = None
    delta: float | None = None
    target: float | None = None
    target_progress_pct: float | None = None
    priority: int | None = None
    status: str | None = None  # "red" | "yellow" | "green"
    trend: str | None = None  # "up" | "down" | "flat"
    coverage_vector: dict[str, float] | None = None  # For tracking consistency (Phase 1)


class EvidenceSource(BaseModel):
    record_type: str
    row_count: int = 0
    earliest: datetime | None = None
    latest: datetime | None = None


class Evidence(BaseModel):
    sources: list[EvidenceSource] = Field(default_factory=list)
    total_rows: int = 0


class SignalCoverage(BaseModel):
    signal_name: str
    completeness: float = 0.0  # 0–1


class Coverage(BaseModel):
    signals: list[SignalCoverage] = Field(default_factory=list)
    missing_sources: list[str] = Field(default_factory=list)
    partial_days: list[str] = Field(default_factory=list)


class Drilldown(BaseModel):
    label: str
    type: str  # "records" | "timeseries"
    params: dict[str, Any] = Field(default_factory=dict)


class PriorityStatus(BaseModel):
    status: str  # "red" | "yellow" | "green"
    progress: float  # 0–100
    trend: str  # "up" | "down" | "flat"
    message: str = ""


class CardEnvelope(BaseModel):
    """Top-level card response object — always constructible."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    schema_version: str = "v0"
    card_type: str
    granularity: Granularity
    time_range: TimeRange
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    summary: str = ""
    signals: list[Signal] = Field(default_factory=list)
    evidence: Evidence = Field(default_factory=Evidence)
    coverage: Coverage = Field(default_factory=Coverage)
    warnings: list[str] = Field(default_factory=list)
    drilldowns: list[Drilldown] = Field(default_factory=list)
    priority_summary: dict[str, PriorityStatus] | None = None
