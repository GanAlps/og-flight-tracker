# OpenSky Auth — Tasks

## Phase 1 — Env loading and credential check

- [x] **1.1** Add `python-dotenv==1.0.1` to `requirements.txt`; install into master venv.
- [x] **1.2** Create `.gitignore` at repo root ignoring `.env`, `__pycache__/`, `.coverage`, `.pytest_cache/`.
- [x] **1.3** Create `.env.example` with `OPENSKY_CLIENT_ID=` and `OPENSKY_CLIENT_SECRET=` placeholders.
- [x] **1.4** Create `tests/conftest.py`: seeds dummy creds at import time and provides autouse fixture for token/cache reset.
- [x] **1.5** `app.py`: `load_dotenv()`, read env vars, raise `RuntimeError` if missing.
- [x] **1.6** Test: importing `app` with creds cleared raises `RuntimeError` (via subprocess).
- [x] **1.7** Full suite green.

## Phase 2 — Token fetch and caching

- [x] **2.1** Added `_TOKEN_URL`, `_token`, `_token_expires_at`, `_get_token()`, `_invalidate_token()` with 30s refresh buffer.
- [x] **2.2** Token tests: fetch, reuse, refresh-on-expiry, upstream failure.
- [x] **2.3** Full suite green.

## Phase 3 — Attach bearer to /states/all + 401 retry

- [x] **3.1** Extracted `_call_opensky(lat1, lon1, lat2, lon2, token)` helper.
- [x] **3.2** `/api/flights` now fetches token, retries once on 401 with a refreshed token.
- [x] **3.3** Tests: bearer header attached, 401 retry success, 401 retry exhausted → upstream_error.
- [x] **3.4** `pytest --cov=app tests/ --cov-fail-under=99` → 29 passed, coverage 99.01%.

## Phase 4 — Documentation

- [x] **4.1** README updated with "OpenSky credentials (required)" setup section.
- [x] **4.2** CLAUDE.md updated with env-var requirement and `.env` convention.
- [ ] **4.3** End-to-end browser verification — requires user to supply real OpenSky creds and restart the app. Open.
