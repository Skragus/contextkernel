"""Tests for CardEnvelope contract."""

from datetime import datetime, timezone

from app.kernel.models import (
    CardEnvelope,
    Granularity,
    Signal,
    TimeRange,
)


def _minimal_envelope(**overrides) -> CardEnvelope:
    defaults = dict(
        card_type="daily_summary",
        granularity=Granularity.daily,
        time_range=TimeRange(
            start=datetime(2026, 2, 15, tzinfo=timezone.utc),
            end=datetime(2026, 2, 16, tzinfo=timezone.utc),
        ),
    )
    defaults.update(overrides)
    return CardEnvelope(**defaults)


class TestCardEnvelopeDefaults:
    def test_schema_version(self):
        env = _minimal_envelope()
        assert env.schema_version == "v0"

    def test_auto_id(self):
        env = _minimal_envelope()
        assert env.id  # non-empty UUID string

    def test_generated_at_utc(self):
        env = _minimal_envelope()
        assert env.generated_at.tzinfo is not None

    def test_empty_signals_by_default(self):
        env = _minimal_envelope()
        assert env.signals == []
        assert env.warnings == []
        assert env.drilldowns == []

    def test_evidence_defaults(self):
        env = _minimal_envelope()
        assert env.evidence.total_rows == 0
        assert env.evidence.sources == []

    def test_coverage_defaults(self):
        env = _minimal_envelope()
        assert env.coverage.missing_sources == []
        assert env.coverage.partial_days == []


class TestCardEnvelopeSerialization:
    def test_roundtrip_json(self):
        env = _minimal_envelope(
            summary="test",
            signals=[
                Signal(
                    name="Steps",
                    record_type="step_count",
                    value=10000.0,
                    unit="steps",
                )
            ],
        )
        data = env.model_dump(mode="json")
        assert data["schema_version"] == "v0"
        assert data["card_type"] == "daily_summary"
        assert len(data["signals"]) == 1
        assert data["signals"][0]["value"] == 10000.0

    def test_envelope_with_zero_signals_is_valid(self):
        env = _minimal_envelope(summary="No data", warnings=["No data in range"])
        data = env.model_dump(mode="json")
        assert data["signals"] == []
        assert "No data in range" in data["warnings"]

    def test_granularity_values(self):
        for g in ("daily", "weekly", "monthly"):
            env = _minimal_envelope(granularity=g)
            assert env.granularity == g
