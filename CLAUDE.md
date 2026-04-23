# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

`og-ft` is a locally-run Flask + Leaflet.js web app that shows real-time flights on a world map. The Flask server is a thin proxy over two free public APIs (OpenSky Network for flights, Nominatim for geocoding); the browser owns all map rendering. No database.

## Required env vars

`app.py` refuses to start without `OPENSKY_CLIENT_ID` and `OPENSKY_CLIENT_SECRET` (raises `RuntimeError` at import). Locally these come from a `.env` file loaded by `python-dotenv`; on Vercel they're set in the project's environment settings. `.env` is gitignored; `.env.example` shows the shape. Test suite uses dummy values seeded in `tests/conftest.py`.

## Commands

Use the shared master venv for everything (see global CLAUDE.md).

```bash
# install / update deps
/home/oshogupta/workspace/master-venv/bin/pip install -r requirements.txt

# run the app (http://localhost:5001)
/home/oshogupta/workspace/master-venv/bin/python app.py

# run all backend tests with coverage
/home/oshogupta/workspace/master-venv/bin/pytest --cov=app tests/ -v

# run a single test
/home/oshogupta/workspace/master-venv/bin/pytest tests/test_app.py::test_flights_returns_normalized_flights -v

# coverage gate required before closing a phase (per DEVELOPMENT.md)
/home/oshogupta/workspace/master-venv/bin/pytest --cov=app tests/ --cov-fail-under=99
```

## Architecture

The whole backend lives in a single file (`app.py`); there is no `app/` package and no blueprints. Keep it that way unless a spec justifies splitting.

Three routes, each a proxy with its own error shape — match the existing shape when adding routes:

- `GET /api/flights?lat1&lon1&lat2&lon2` → proxies OpenSky `/states/all`. Returns `{flights, count, timestamp}` on success, or `{error: "zoom_required"|"upstream_error"}` otherwise. Invalid params return HTTP 400 with `{error: "invalid_params"}`.
- `GET /api/geocode?q=` → proxies Nominatim, returns a single result.
- `GET /api/suggestions?q=` → proxies Nominatim, returns up to 5 autocomplete items. Silently returns `[]` on any failure (shorter query, upstream error, etc.) — do **not** add error envelopes here; the frontend expects a plain list.

### Two invariants to preserve

1. **OpenSky rate limiting lives server-side.** `app.py` uses module-level `_cache` (dict keyed by bbox rounded to 1 decimal) and `_last_fetch` (unix time) to enforce 1 request per `_RATE_LIMIT_SECONDS` (10s). The frontend auto-refreshes every 15s and disables its manual button for 10s — these numbers are coupled. If you change the server rate limit, update `map.js` timers and the README accordingly.
2. **Bounding-box area guard.** `_BBOX_AREA_LIMIT = 25` (degrees²) rejects over-zoomed-out requests with `zoom_required` before hitting OpenSky. The frontend shows a toast and clears markers on that response — don't turn it into an HTTP error.

### Frontend (`static/map.js`)

Single IIFE. All state (markers array, cooldown flag, timer handles) is module-local. Map events that can trigger refetches (`moveend`, manual button, autocomplete selection) all route through `fetchAndRenderFlights`, which owns cooldown + countdown + loading overlay. When adding new triggers, call that function rather than fetching directly.

The plane icon is an inline SVG built in `buildIcon()` — `static/icons/plane.svg` is reference only and not loaded at runtime.

### Nominatim User-Agent

Both `/api/geocode` and `/api/suggestions` send `User-Agent: og-ft-flight-tracker/1.0`. Nominatim's usage policy requires a unique UA; don't remove it.

## Specs

Feature specs live under `specs/<feature-name>/` per the spec-driven workflow in `~/.claude/DEVELOPMENT.md`. Existing: `specs/flight-tracker/` (the initial MEDIUM-complexity full-feature build) and `specs/search-autocomplete/` (a simple-change addition). Read the relevant spec before changing behavior in that area.

## Tests

`tests/test_app.py` mirrors the three routes and uses `unittest.mock.patch("app.requests.get")` for all upstream calls — never hit the network in tests. The `reset_cache` autouse fixture clears `_cache` and `_last_fetch` between tests; rely on it rather than re-clearing manually.
