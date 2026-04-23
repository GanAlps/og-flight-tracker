# UX Improvements — Tasks

## Phase 1 — Backend: rate_limited response

- [x] **1.1** `app.py`: 429 branch returns `{"error": "rate_limited", ...}`, placed after the 401-retry so a 401→refresh→429 also lands here.
- [x] **1.2** Tests: 429 → rate_limited JSON; 429 does not invalidate the cached token.
- [x] **1.3** `pytest --cov=app tests/ --cov-fail-under=99` → 31 passed, coverage 99.03%.

## Phase 2 — Frontend: pause auto-refresh on throttle

- [x] **2.1** `autoRefreshPaused` flag and `stopAutoRefresh()` helper added.
- [x] **2.2** `rate_limited` handler in `fetchAndRenderFlights`: clears markers, stops auto-refresh, warn toast.
- [x] **2.3** On any successful fetch while paused: unset flag, `scheduleAutoRefresh()`, `resetCountdown()`.

## Phase 3 — Frontend: explicit pinch-to-zoom options

- [x] **3.1** `L.map(...)` now passes `touchZoom: true` and `scrollWheelZoom: true` explicitly.

## Phase 4 — Frontend: geolocation on boot

- [x] **4.1** Boot now schedules auto-refresh, then calls `getCurrentPosition`; on success, `setView(userLocation, 10)` (moveend fetches); on error/unsupported, falls back to the default world-view fetch.

## Phase 5 — Manual verification (user)

- [ ] **5.1** Reload app: geolocation prompt → map centers on user, nearby flights visible.
- [ ] **5.2** Trigger a 429 naturally or by hammering refresh: "Rate limited" toast, auto-refresh halts, manual click resumes.
- [ ] **5.3** Pinch-to-zoom works on trackpad/touch.
