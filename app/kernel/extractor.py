"""Extract numeric values from health_records rows using RECORD_TYPE_CONFIG."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from app.kernel.record_type_map import get_config


def _first_numeric(data: Any) -> float | None:
    """Walk a dict/list and return the first numeric value found."""
    if isinstance(data, (int, float)) and not isinstance(data, bool):
        return float(data)
    if isinstance(data, dict):
        for v in data.values():
            result = _first_numeric(v)
            if result is not None:
                return result
    if isinstance(data, (list, tuple)):
        for item in data:
            result = _first_numeric(item)
            if result is not None:
                return result
    return None


def _resolve_key(data: Any, key: str) -> Any:
    """Resolve a dot-path key like 'foo.bar' or 'list.0.field' in nested dicts/lists."""
    current = data
    for part in key.split("."):
        if isinstance(current, dict):
            current = current.get(part)
        elif isinstance(current, (list, tuple)):
            try:
                current = current[int(part)]
            except (ValueError, IndexError):
                return None
        else:
            return None
    return current


def extract_value(record: dict[str, Any]) -> float | None:
    """Extract a single numeric value from a health_records row.

    Uses RECORD_TYPE_CONFIG for known types, falls back to first-numeric heuristic.
    Returns None on any failure — never raises.
    """
    try:
        rt = record.get("record_type", "")
        cfg = get_config(rt)
        data = record.get("data")

        if data is None:
            return None

        # If data is stored as a raw string, skip (shouldn't happen with jsonb)
        if not isinstance(data, dict):
            return _first_numeric(data)

        if cfg.value_key is not None:
            raw = _resolve_key(data, cfg.value_key)
            if raw is None:
                return _first_numeric(data)
            if isinstance(raw, (int, float)) and not isinstance(raw, bool):
                return float(raw)
            # Try to parse string-encoded numbers
            if isinstance(raw, str):
                try:
                    return float(raw)
                except ValueError:
                    return None
            return None

        # Fallback: first numeric value in the dict
        return _first_numeric(data)
    except Exception:
        return None


def extract_batch(
    records: list[dict[str, Any]],
) -> list[tuple[datetime, float]]:
    """Extract (timestamp, value) pairs, skipping rows where extraction fails."""
    pairs: list[tuple[datetime, float]] = []
    for rec in records:
        val = extract_value(rec)
        if val is not None:
            ts = rec.get("start_date")
            if ts is not None:
                pairs.append((ts, val))
    return pairs
