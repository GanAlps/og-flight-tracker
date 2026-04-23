# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

`og-flight-tracker` is a locally-run Flask + Leaflet.js web app that shows real-time flights on a world map. The Flask server is a thin authenticated proxy over OpenSky Network (OAuth2 client-credentials, for flights) and Nominatim (for geocoding/autocomplete); the browser owns all map rendering. No database.

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

- `GET /api/flights?lat1&lon1&lat2&lon2` → proxies OpenSky `/states/all`. Returns `{flights, count, timestamp}` on success, or `{error: "zoom_required"|"rate_limited"|"upstream_error"}` on the various degraded states. Invalid params return HTTP 400 with `{error: "invalid_params"}`.
- `GET /api/geocode?q=` → proxies Nominatim, returns a single result.
- `GET /api/suggestions?q=` → proxies Nominatim, returns up to 5 autocomplete items. Silently returns `[]` on any failure (shorter query, upstream error, etc.) — do **not** add error envelopes here; the frontend expects a plain list.

### Invariants to preserve

1. **OpenSky rate limiting lives server-side.** `app.py` uses a module-level `OrderedDict` `_cache` keyed by rounded bbox, storing `(fetch_time, result)` per entry, with `_CACHE_TTL_SECONDS = 10` and `_CACHE_MAX_ENTRIES = 128` LRU eviction. The frontend auto-refreshes every 60s, resets that interval on every successful fetch, and disables the manual button for 10s after a real upstream call. If you change the server TTL, update `map.js` timers and the README.
2. **Bounding-box area guard.** `_BBOX_AREA_LIMIT = 25` (degrees²) rejects over-zoomed-out requests with `zoom_required` before hitting OpenSky. The frontend shows a toast and clears markers on that response — don't turn it into an HTTP error.
3. **OpenSky OAuth2.** `_get_token()` caches a bearer for its ~30-min lifetime (refreshed 30s early); `/api/flights` retries exactly once on a 401 by invalidating the token. The token cache is module-level and does not persist across Vercel cold starts — that's accepted; don't add Redis to fix it without a spec.
4. **No `innerHTML` for third-party strings.** Anything originating from OpenSky (callsign, country) or Nominatim (display_name) must go through `escapeHtml()` or be assigned via `textContent`. See `static/map.js`.

### Frontend (`static/map.js`)

Single IIFE. All state (markers array, cooldown flag, timer handles) is module-local. Map events that can trigger refetches (`moveend`, manual button, autocomplete selection) all route through `fetchAndRenderFlights`, which owns cooldown + countdown + loading overlay. When adding new triggers, call that function rather than fetching directly.

The plane icon is an inline SVG built in `buildIcon()` — `static/icons/plane.svg` is reference only and not loaded at runtime.

### Nominatim User-Agent

Both `/api/geocode` and `/api/suggestions` send `User-Agent: og-ft-flight-tracker/1.0`. Nominatim's usage policy requires a unique UA; don't remove it.

## Specs

Feature specs live under `specs/<feature-name>/` per the spec-driven workflow in `~/.claude/DEVELOPMENT.md`. Existing: `flight-tracker` (initial full-feature build), `search-autocomplete`, `opensky-auth` (OAuth2), `ux-improvements` (rate-limit handling, geolocation, pinch), `ux-polish` (welcome header, my-location icon, 60s cadence, toast-once). Read the relevant spec before changing behavior in that area.

## Tests

`tests/test_app.py` mirrors the three routes and uses `unittest.mock.patch("app.requests.get")` / `...post` for all upstream calls — never hit the network in tests. `tests/conftest.py` sets dummy OpenSky credentials in `os.environ` before `app` is imported so the import-time credential check passes, and its `reset_app_state` autouse fixture clears `_cache` and pre-seeds a valid `_token` / `_token_expires_at` between tests. Rely on the fixture rather than re-clearing manually.
