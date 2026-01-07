# playwright_flake_triage_poc

Playwright Flake Lab PoC: reproduce a deterministic UI flake (overlay intercept), collect evidence (logs/traces), and validate a targeted fix with before/after success rates.

## Scope

This repo contains two related PoCs:

1. **UI flake triage (Playwright)**
   Reproduce a UI flake where a transient overlay intercepts clicks, then validate a deterministic fix (wait for overlay detachment) without relying on blanket timeouts.

2. **API smoke/contract (pytest + httpx)**
   Validate FastAPI mock endpoints (`/health`, `/api/items`) in a CI-friendly way.

## Project layout

- `backend/` — FastAPI mock API + pytest API tests
  - `app/main.py` — FastAPI app (`FASTAPI_APP=app.main:app`)
  - `tests/` — pytest tests (health/items)
  - `requirements.txt` — server deps (FastAPI/uvicorn/jinja2)
  - `requirements-dev-api.txt` — API test deps (pytest/httpx/pytest-anyio)
  - `requirements-dev-e2e.txt` — E2E deps (playwright)
- `scripts/` — Playwright flake trial runner
- `artifacts/` — traces and run outputs

## Environments (venv split)

### API tests venv (`backend/.venv_api`)

Used for pytest-based API smoke/contract tests.

```bash
cd backend
python3 -m venv .venv_api
source .venv_api/bin/activate
python -m pip install -U pip
python -m pip install -r requirements.txt
python -m pip install -r requirements-dev-api.txt
```

Run API tests:

```bash
cd backend
source .venv_api/bin/activate
FASTAPI_APP="app.main:app" python -m pytest -q
```

### E2E venv (`backend/.venv_e2e`)

Used for Playwright + (optionally) running the local backend for UI trials.

```bash
cd backend
python3 -m venv .venv_e2e
source .venv_e2e/bin/activate
python -m pip install -U pip
python -m pip install -r requirements.txt
python -m pip install -r requirements-dev-e2e.txt
python -m playwright install chromium firefox
```

Note: On macOS 13, WebKit may be frozen. This repo uses Chromium/Firefox for local runs.

## Quickstart

### 1) Run backend (for UI / Playwright)

```bash
cd backend
source .venv_e2e/bin/activate
uvicorn app.main:app --host 127.0.0.1 --port 8004
```

Base URL: `http://127.0.0.1:8004`

Backend server must be started from ./backend (required for module path / templates)


### 2) Run API tests (pytest)

```bash
cd backend
source .venv_api/bin/activate
FASTAPI_APP="app.main:app" python -m pytest -q
```

### 3) Run UI flake trials (Playwright)

#### Goal

Reproduce and triage a UI flake where a transient overlay intercepts clicks, then demonstrate a deterministic fix (wait for overlay detachment) without relying on blanket timeouts.

#### Flake injection (test-side overlay)

- Method: Inject a transient full-page overlay `#__flake_overlay` that intercepts pointer events
- Duration: 300ms
- Probability: 0.3 per run
- Seed: 42
- Flow: list → detail → Approve
- Runs: 50
- Base URL: `http://127.0.0.1:8004`

#### How to run (UI)

**Before (naive click)**

Naively clicks Approve with a short timeout. When the overlay is injected, the click is blocked and fails.

```bash
rm -rf artifacts/traces/*
rm -f artifacts/playwright_runs.jsonl
FLAKE_STRATEGY=naive FLAKE_OVERLAY_MS=300 FLAKE_OVERLAY_PROB=0.3 TEST_FLAKE_SEED=42 \
  python scripts/run_flake_trials.py
```

**After (wait overlay detached)**

Waits until the overlay is removed before clicking Approve.

```bash
rm -rf artifacts/traces/*
rm -f artifacts/playwright_runs.jsonl
FLAKE_STRATEGY=wait FLAKE_OVERLAY_MS=300 FLAKE_OVERLAY_PROB=0.3 TEST_FLAKE_SEED=42 \
  python scripts/run_flake_trials.py
```

#### Results (before / after)

| Scenario | Run dir | OK | FAIL | Success | Overlay injected | Top failure reason |
|----------|---------|----|----|---------|------------------|-------------------|
| Before (naive click) | artifacts/runs/20260106_172219_before_naive | 30 | 20 | 60% | 20 | click_timeout (overlay intercept) |
| After (wait overlay detached) | artifacts/runs/20260106_172954_after_wait | 50 | 0 | 100% | 20 | n/a |

**Interpretation:** In the naive strategy, every injected-overlay run failed (20/20), while all non-injected runs succeeded (30/30). After adding an explicit wait for overlay detachment, the same injection pattern achieved 50/50 success.

#### Evidence (logs / traces)

Each run directory contains:

- `playwright_runs.jsonl`: one JSON record per trial (ok/fail, error_type, step, overlay flags)
- `traces/`: fail-only Playwright traces (before run only in this dataset)

Example failure signature (before):

```
Locator.click: Timeout 200ms exceeded
#__flake_overlay intercepts pointer events
```

## Notes

### Rendering vs. DOM-level flakiness

This PoC targets a DOM/event-level failure mode (click interception by an overlay). In our setup, enabling Jinja2 (server-side HTML templating) did not materially change the DOM structure or the interaction flow, so the before/after behavior remained consistent. If the UI implementation changes DOM structure, selectors or timing assumptions may need to be updated accordingly.