# Observability — Tasks

## Phase 1 — Logger setup + startup confirmation

- [x] **1.1** `logging.basicConfig(level=logging.INFO, ...)` added at import in `app.py`.
- [x] **1.2** Credential-loaded confirmation log (lengths only, values never touched).
- [x] **1.3** Suite green.

## Phase 2 — Token layer

- [x] **2.1** `_get_token`: pre-POST `INFO` with reason, `app.logger.exception` on failure, success log with `expires_in`.
- [x] **2.2** `_invalidate_token(reason="...")`: `WARNING` only when a real token is being dropped.
- [x] **2.3** `/api/flights` 401 branch passes `reason="states-endpoint-401"`.
- [x] **2.4** Suite green.

## Phase 3 — Route-level logging

- [x] **3.1** `/api/flights`: `INFO` on zoom guard, `WARNING` on 401-retry trigger and 429, `app.logger.exception` on any upstream failure.
- [x] **3.2** `/api/geocode`: `INFO` on not-found (length only), `app.logger.exception` on upstream failure.
- [x] **3.3** `/api/suggestions`: `WARNING` with `exc_info=True` on upstream failure.
- [x] **3.4** Suite green — 33 passed, coverage 99.23%.

## Phase 4 — Frontend console logging

- [x] **4.1** `console.info` on zoom_required / rate_limited / resume-after-success; `console.error` on upstream_error and fetch catch; `console.info/warn` on geolocation boot + My-Location button.

## Phase 5 — Doc sync

- [x] **5.1** `CLAUDE.md`: new "Logging" section capturing the conventions.

## Phase 6 — Manual verification (user)

- [ ] **6.1** Redeploy to Vercel.
- [ ] **6.2** Reload app; confirm a real traceback appears in Vercel logs when `/api/flights` fails.
