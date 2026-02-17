## ContextKernel — Final Build Plan (new repo)

### Goal

Create a standalone FastAPI service called **ContextKernel** that:

* reads raw telemetry from existing Postgres (`health_records`)
* computes rollups + baselines + coverage
* returns **CardEnvelope v0** responses
* supports **presets** (named bundles)
* **never crashes** due to missing/partial data (it returns warnings + coverage instead)

### Non-goals (MVP)

* no DB migrations
* no caching/pre-aggregation
* no ML/anomalies/seasonality
* no DSL / plugin runtime
* no calendar/GPS/app-usage connectors yet

---

## Tech stack

* **Python 3.12**
* **FastAPI**
* **Pydantic v2**
* **SQLAlchemy 2.x** (async) + asyncpg
* **pytest** (+ httpx for endpoint tests)
* Railway deploy (service + env vars)

Why Python: fastest path to “real working thing”, easy testing, easy JSON contract work, easy iteration. Go is great when you’re stable; this is still evolving.

---

## Repo shape (do this first)

```
contextkernel/
  app/
    __init__.py
    main.py
    config.py
    db.py
    kernel/
      __init__.py
      models.py
      record_type_map.py
      connector.py
      extractor.py
      features.py
      builders.py
      presets.py
      router.py
  tests/
    conftest.py
    test_models.py
    test_features.py
    test_extractor.py
    test_builders.py
    test_endpoints.py
  pyproject.toml
  README.md
```

---

## Environment variables (Railway)

* `DATABASE_URL` (points to the existing Postgres)
* `DEFAULT_TZ` (default `UTC`)
* optional later: `KERNEL_API_KEY` (if you want auth now; can also sit behind Railway private networking)

---

## Phase 0 — Data Recon (reality check)

**Goal:** Build `RECORD_TYPE_CONFIG` based on what’s actually in `health_records`.

Tasks:

1. Query DB:

* distinct `record_type`
* sample `data` JSON for each

2. Create `app/kernel/record_type_map.py`:

* `RECORD_TYPE_CONFIG: dict[str, {agg, value_key}]`
* `DEFAULT_CONFIG` fallback:

  * agg: `"avg"`
  * value extraction: “first numeric value found” (best-effort)

Acceptance:

* every known record_type has a config entry
* unknown types don’t crash extraction

---

## Phase 1 — CardEnvelope contract (Pydantic)

**File:** `app/kernel/models.py`

Implement `CardEnvelope v0` + supporting models.

Must include:

* `time_range` (start/end/timezone)
* `granularity` (`daily|weekly|monthly`)
* `summary` (reporting-only strings)
* `signals` (value/baseline/delta/target optional)
* `evidence` (sources used + row counts + coverage metrics)
* `coverage`

  * per-signal completeness (0–1)
  * `missing_sources[]`
  * `partial_days[]`
* `warnings[]` (non-fatal problems)
* `drilldowns[]` (handles)
* `schema_version="v0"`
* auto `id` (UUID) and `generated_at` (UTC)

Rule:

* Envelope should always be constructible, even with zero signals.

---

## Phase 2 — Connector + Extractor + Features

### 2.1 Connector (DB access)

**File:** `app/kernel/connector.py`

Async functions:

* `get_record_types(start,end)`
* `fetch_records(record_type?, start,end)`
* `check_availability(record_types,start,end)` → per-type counts + dates

Rules:

* always return empty results if nothing found
* missing data never raises

### 2.2 Extractor (JSON → floats)

**File:** `app/kernel/extractor.py`

Functions:

* `extract_value(record) -> float|None`
* `extract_batch(records) -> list[(timestamp, value)]`

Rules:

* uses RECORD_TYPE_CONFIG + fallback
* any failure returns None, no exceptions

### 2.3 Feature functions (pure math)

**File:** `app/kernel/features.py`

Pure, stateless:

* trailing average
* baseline computation dispatch (daily=7, weekly=4, monthly=3)
* delta computation
* coverage percentage
* partial day detection

Rules:

* empty input returns None/0.0
* never raises

---

## Phase 3 — Builders (the Kernel)

**File:** `app/kernel/builders.py`

Three builders only:

* `build_daily_summary(db, date, tz) -> CardEnvelope`
* `build_weekly_overview(db, start_date, tz) -> CardEnvelope`
* `build_monthly_overview(db, year, month, tz) -> CardEnvelope`

Builder responsibilities:

* define range boundaries in `tz`, query in UTC
* group records by record_type
* extract numeric values
* aggregate per record_type (sum/avg)
* compute baselines (prior 7 days / 4 weeks / 3 months)
* compute deltas when baseline exists
* compute coverage + warnings:

  * missing_sources: known record types that have zero rows in target range
  * partial_days: days with suspiciously low record counts (below median)
  * warning for “no data in range”, “future range”, “baseline insufficient”, etc.
* add drilldowns:

  * “records for record_type in range”
  * “timeseries for metric”
  * etc.

**Graceful degradation rule (hard):**

* no data → return valid envelope with empty signals, strong warning, coverage communicates it
* baseline missing → baseline=None delta=None, warning

---

## Phase 4 — Presets + Router

### 4.1 Presets

**File:** `app/kernel/presets.py`

Hardcoded dict:

* `daily_brief` → [daily_summary]
* `weekly_health` → [weekly_overview]
* `monthly_overview` → [monthly_overview]

Presets are configuration only. No formulas.

### 4.2 Router

**File:** `app/kernel/router.py`

Routes:

* `GET /kernel/cards/{card_type}`

  * returns **one** CardEnvelope
  * query: `from`, `to`, `tz` (date-only expands to full day)
  * invalid dates → 422
  * unknown card → 404

* `GET /kernel/presets`

* `GET /kernel/presets/{id}`

* `GET /kernel/presets/{id}/run`

  * returns list[CardEnvelope]

### 4.3 Integrate into app

**File:** `app/main.py`

* create FastAPI app
* include kernel router

---

## Phase 5 — Tests (minimum but real)

* `test_models.py`: envelope serializes, defaults correct
* `test_features.py`: math edge cases
* `test_extractor.py`: known types + unknown types + bad JSON
* `test_builders.py`: mock connector results; verify:

  * correct envelope shape
  * zero-data graceful case
  * baseline missing behaves
  * coverage/warnings populated
* `test_endpoints.py`: FastAPI TestClient, verify 200/404/422

---

## Deployment plan (Railway)

* Create new Railway service from the `contextkernel` repo
* Set `DATABASE_URL` to the **existing** Postgres
* Run with `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
* Smoke test:

  * `/kernel/presets`
  * `/kernel/cards/daily_summary?from=2026-02-15&to=2026-02-15`
  * `/kernel/presets/daily_brief/run?...`

