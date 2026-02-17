"""Extract numeric values from health_connect_daily rows."""

from __future__ import annotations

from datetime import date
from typing import Any

from app.kernel.signal_map import SignalConfig, get_signal_config, list_signals


def _resolve_path(data: Any, path: str) -> Any:
    """Resolve dot-path like 'weight_kg' or '0.duration_minutes' in dicts/lists."""
    current = data
    for part in path.split("."):
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


def _to_float(raw: Any) -> float | None:
    if raw is None:
        return None
    if isinstance(raw, (int, float)) and not isinstance(raw, bool):
        return float(raw)
    if isinstance(raw, str):
        try:
            return float(raw)
        except ValueError:
            return None
    return None


def extract_signal(row: dict[str, Any], config: SignalConfig) -> float | None:
    """Extract a single signal value from a health_connect_daily row."""
    try:
        col_val = row.get(config.column)
        if config.path is None:
            raw = col_val
        else:
            if col_val is None or not isinstance(col_val, (dict, list)):
                return None
            raw = _resolve_path(col_val, config.path)
        return _to_float(raw)
    except Exception:
        return None


def extract_signals_from_row(row: dict[str, Any]) -> dict[str, float]:
    """Extract all configured signals from one row. Skips missing values."""
    out: dict[str, float] = {}
    for name in list_signals():
        cfg = get_signal_config(name)
        if cfg is None:
            continue
        val = extract_signal(row, cfg)
        if val is not None:
            out[name] = val
    return out


def extract_signal_series(
    rows: list[dict[str, Any]],
) -> dict[str, list[float]]:
    """Extract per-signal value lists from rows. Rows ordered by date."""
    series: dict[str, list[float]] = {name: [] for name in list_signals()}
    for row in rows:
        vals = extract_signals_from_row(row)
        for name, v in vals.items():
            series[name].append(v)
    return series
