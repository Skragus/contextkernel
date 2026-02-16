# ContextKernel

Standalone FastAPI service that reads telemetry from an existing Postgres `health_records` table, computes rollups + baselines + coverage, and returns **CardEnvelope v0** responses.

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
| `GET` | `/kernel/cards/{type}` | Single CardEnvelope (`daily_summary`, `weekly_overview`, `monthly_overview`) |
| `GET` | `/kernel/presets` | List available presets |
| `GET` | `/kernel/presets/{id}` | Preset detail |
| `GET` | `/kernel/presets/{id}/run` | Execute preset, returns `list[CardEnvelope]` |
| `GET` | `/health` | Health check |

### Query parameters

- `from` — start date (YYYY-MM-DD, required)
- `to` — end date (YYYY-MM-DD, required)
- `tz` — timezone (default: `UTC`)

### Example

```
GET /kernel/cards/daily_summary?from=2026-02-15&to=2026-02-15
GET /kernel/presets/daily_brief/run?from=2026-02-15&to=2026-02-15
```

## Project structure

```
app/
  main.py              # FastAPI app
  config.py            # Settings (DATABASE_URL, DEFAULT_TZ)
  db.py                # SQLAlchemy async engine
  kernel/
    models.py          # CardEnvelope v0 Pydantic contract
    record_type_map.py # RECORD_TYPE_CONFIG + DEFAULT_CONFIG
    connector.py       # Async DB queries
    extractor.py       # JSON -> float extraction
    features.py        # Pure math (aggregate, baseline, delta, coverage)
    builders.py        # Card builders (daily/weekly/monthly)
    presets.py         # Hardcoded preset definitions
    router.py          # HTTP routes
tests/
  conftest.py          # Fixtures + fake session
  test_models.py       # Envelope contract tests
  test_features.py     # Math edge cases
  test_extractor.py    # Known/unknown types + bad JSON
  test_builders.py     # Mock connector, verify shape/graceful degradation
  test_endpoints.py    # HTTP 200/404/422 tests
```

## Design rules

- One call to `/kernel/cards/{type}` returns exactly one `CardEnvelope`.
- Missing or partial data never causes a 500 — returns valid envelopes with coverage + warnings.
- No DB migrations, no caching, no ML.
- `RECORD_TYPE_CONFIG` maps known types; `DEFAULT_CONFIG` handles unknowns via first-numeric heuristic.

## Auth (optional)

Set `KERNEL_API_KEY` to require API key auth on all kernel endpoints. When set, clients must pass:
- `X-API-Key: <key>`, or
- `Authorization: Bearer <key>`

When not set, kernel endpoints are unauthenticated.

## Deploy (Railway)

1. Create new Railway service pointing to this repo
2. Set `DATABASE_URL` to the existing Postgres
3. (Optional) Set `KERNEL_API_KEY` for auth
