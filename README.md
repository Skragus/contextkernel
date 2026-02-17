# ContextKernel

Standalone FastAPI service that reads telemetry from Postgres `health_connect_daily` table, computes rollups + baselines + coverage, and returns **CardEnvelope v0** responses.

## Quick start

```bash
# Install
pip install -e ".[dev]"

# Set env
export DATABASE_URL="postgresql+asyncpg://user:pass@host:5432/db"

# Run
uvicorn app.main:app --host 0.0.0.0 --port 8000

# Test (no DB needed)
pytest tests/ -v
```

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/` | Root manifest (links to docs, health, kernel endpoints) |
| `GET` | `/kernel/cards/{type}` | Single CardEnvelope (`daily_summary`, `weekly_overview`, `monthly_overview`) |
| `GET` | `/kernel/presets` | List available presets |
| `GET` | `/kernel/presets/{id}` | Preset detail |
| `GET` | `/kernel/presets/{id}/run` | Execute preset, returns `list[CardEnvelope]` |
| `GET` | `/kernel/goals` | List configured goals (config-only) |
| `GET` | `/kernel/goals/progress` | Compact goal progress snapshot (wraps `daily_summary`) |
| `GET` | `/health` | Health check |

### Query parameters

- `from` — start date (YYYY-MM-DD, required for card/preset/goal progress)
- `to` — end date (YYYY-MM-DD, required for card/preset/goal progress)
- `tz` — timezone (default: `UTC`)
- `device_id` — optional device filter for cards/presets/goal progress

### Examples

```bash
curl "http://localhost:8000/kernel/cards/daily_summary?from=2026-02-15&to=2026-02-15"

curl "http://localhost:8000/kernel/presets/daily_brief/run?from=2026-02-15&to=2026-02-15"

curl "http://localhost:8000/kernel/goals"

curl "http://localhost:8000/kernel/goals/progress?from=2026-02-15&to=2026-02-15"
```

## Project structure

```
app/
  main.py              # FastAPI app
  config.py            # Settings (DATABASE_URL, DEFAULT_TZ)
  db.py                # SQLAlchemy async engine
  kernel/
    models.py          # CardEnvelope v0 Pydantic contract (+ goal fields)
    signal_map.py      # Signal config for health_connect_daily columns
    connector.py       # Async DB queries
    extractor.py       # JSON -> float extraction
    features.py        # Pure math (aggregate, baseline, delta, coverage, goals)
    builders.py        # Card builders (daily/weekly/monthly + goals wiring)
    presets.py         # Hardcoded preset definitions
    goals_config.py    # Config-only goal definitions (T1–T3)
    router.py          # HTTP routes (cards, presets, goals)
tests/
  conftest.py          # Fixtures + fake session
  test_models.py       # Envelope contract tests
  test_features.py     # Math edge cases
  test_extractor.py    # Known/unknown types + bad JSON
  test_builders.py     # Mock connector, verify shape/graceful degradation
  test_endpoints.py    # HTTP 200/404/422 + auth + goals endpoints
  test_goals.py        # Goal config, helpers, and builder integration
```

## Design rules

- One call to `/kernel/cards/{type}` returns exactly one `CardEnvelope`.
- Missing or partial data never causes a 500 — returns valid envelopes with coverage + warnings.
- No DB migrations, no caching, no ML.
- Table: `health_connect_daily` (device_id, date, source_type, raw_data JSONB). All metrics live in `raw_data`. Optional `device_id` query param to filter.

## Goals system (config-only)

- Goals are defined **in code only** in `app/kernel/goals_config.py` (no DB schema changes).
- Current priorities:
  - **P1**: tracking consistency (virtual signal `tracking_consistency`, derived from how often calories/weight are logged).
  - **P2**: calories (`calories_total`, target is an upper bound).
  - **P3**: steps (`steps_total`, target is a lower bound).
- When a goal is configured for a signal, builders automatically attach:
  - `target`, `target_progress_pct`, `priority`, `status` (`red`/`yellow`/`green`), `trend` (`up`/`down`/`flat`) on that `Signal`.
  - A `priority_summary` map on each `CardEnvelope` (e.g. `P1`, `P2`, `P3` rollups).
- `/kernel/goals` exposes the raw config; `/kernel/goals/progress` returns a compact snapshot built on top of the `daily_summary` card.

## Auth (optional)

Set `KERNEL_API_KEY` to require API key auth on all kernel endpoints. When set, clients must pass:
- `X-API-Key: <key>`, or
- `Authorization: Bearer <key>`

When not set, kernel endpoints are unauthenticated.

## Deploy (Railway)

1. Create new Railway service pointing to this repo
2. Set `DATABASE_URL` to the existing Postgres
3. (Optional) Set `KERNEL_API_KEY` for auth
