# Breathe ESG — Data Ingestion & Review Prototype

Django REST + React app that ingests emissions activity data from three source types, normalises it, and surfaces a review dashboard where analysts can approve rows before they're locked for audit.

## Demo credentials

| User | Password | Role |
|------|----------|------|
| admin | admin123 | Superuser |
| analyst | analyst123 | Analyst |

## Architecture

```
backend/   Django 4.2 + DRF + SQLite (dev) / PostgreSQL (prod)
frontend/  React 18 + Vite + Tailwind CSS
```

### Three data sources

| Source | Format | Scope |
|--------|--------|-------|
| SAP Fuel & Procurement | Tab-delimited MB51 flat file export (German locale) | 1 |
| Utility Electricity | Billing summary CSV | 2 |
| Corporate Travel | Concur expense report CSV | 3 |

## Running locally

Requires [uv](https://docs.astral.sh/uv/getting-started/installation/) and Node 18+.

```bash
# One command starts both servers
./dev.sh
```

Or manually:

```bash
# Backend
cd backend
uv sync
uv run python manage.py migrate
uv run python manage.py seed
uv run python manage.py runserver

# Frontend (separate terminal)
cd frontend
npm install
npm run dev
```

Open http://localhost:5173 — Vite proxies `/api` calls to Django on port 8000.

## Testing ingestion

Sample files are in `sample_data/`. Upload them at the Ingest Data page:

| File | Source |
|------|--------|
| `sap_fuel_DE_UK_2024Q1.txt` | SAP Fuel & Procurement |
| `utility_billing_Q1_2024.csv` | Utility Electricity |
| `travel_concur_Q1_2024.csv` | Corporate Travel |

## Running the test suite

```bash
# Server must be running first (./dev.sh)
cd backend && uv run python ../tests/run_tests.py
```

135 tests, all pass.

## Deploying to Render (free)

1. Push this repo to GitHub
2. Go to [render.com](https://render.com) → New → Blueprint
3. Connect your GitHub repo — Render picks up `render.yaml` automatically
4. Click **Apply** — Render creates the backend service, frontend static site, and PostgreSQL database
5. Wait ~5 minutes for the first deploy to finish

The backend URL (e.g. `https://esg-backend.onrender.com`) is automatically passed to the frontend build as `VITE_API_URL`.

> **Free tier note:** The backend web service spins down after 15 minutes of inactivity. The first request after sleep takes ~30 seconds. The PostgreSQL database is free for 90 days, after which it requires upgrading to a paid plan.

## Design documents

- `MODEL.md` — Data model and design rationale
- `DECISIONS.md` — Every ambiguity resolved with reasoning
- `TRADEOFFS.md` — Three things deliberately not built
- `SOURCES.md` — Research on each data source format
- `TESTCASES.md` — All 135 test cases with pass/fail status
