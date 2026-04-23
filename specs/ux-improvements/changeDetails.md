# UX Improvements — Change Details

## Overview

Four small improvements to make rate-limiting recoverable, make first-load feel local, and make map navigation feel right on trackpads/touch devices.

1. Distinguish OpenSky 429 (throttled) from generic upstream failures with its own error shape and user-facing message.
2. On throttle, stop the 15-s auto-refresh loop and only refresh on user action; resume automatically after the next successful fetch.
3. Explicitly enable pinch-to-zoom in the Leaflet options (documentation-level; defaults already permit it).
4. On first load, request browser geolocation and center the map on the user's location; fall back to the current default world view if denied/unavailable.

No backend architectural change; no new dependencies.

## Constraints and edge cases

- **Throttle detection is on `/states/all` only.** If the token endpoint (`_TOKEN_URL`) returns 429 on the rare path where we re-fetch tokens during a burst, that stays mapped to `upstream_error`. Not worth the added branching.
- **Error envelope is additive.** New `{"error": "rate_limited", "message": ...}` response is a 200 JSON, matching the existing `zoom_required` pattern so the frontend can branch on `data.error`.
- **Auto-refresh resumes on the first success after throttle**, whether that success comes from the manual button or from a `moveend`-triggered fetch. "User action only" holds while throttled; once a request lands, we're back to the normal 15-s cadence.
- **Geolocation is best-effort.** If the browser has no geolocation support, the user denies, or the request times out (5s), we fall back to the existing world-view boot path. No second prompt on refusal — browsers cache the decision themselves.
- **Initial double-fetch is avoided.** With geolocation enabled, the boot path skips the immediate `fetchAndRenderFlights()` at default zoom and lets `setView(userLocation, 10)` trigger a single fetch via the existing `moveend` debounced handler. On denial, the old immediate-fetch path runs.
- **Pinch-to-zoom on Mac trackpad** already works through Leaflet's scroll-wheel handler (ctrl+wheel). On touch devices, `touchZoom` is on by default. We'll set both options explicitly for clarity.

## Solution

### 1. Distinct throttled error (backend)

In `app.py`, between the 401-retry block and `resp.raise_for_status()`, add:

```python
if resp.status_code == 429:
    return jsonify({
        "error": "rate_limited",
        "message": "OpenSky rate limit reached. Auto-refresh is paused — retry manually.",
    })
```

### 2. Pause auto-refresh on throttle (frontend)

`static/map.js` changes:

- Add `let autoRefreshPaused = false;` to module state.
- Add `stopAutoRefresh()` helper that clears both `autoRefreshTimer` and `countdownTimer`, sets status text to `"Rate limited — tap ↺ to retry"`, and sets `autoRefreshPaused = true`.
- In `fetchAndRenderFlights()`:
  - When `data.error === "rate_limited"`: `clearMarkers()`, `stopAutoRefresh()`, `showToast(data.message, "warn")`, return.
  - On any successful branch (i.e., the success-path end): if `autoRefreshPaused`, clear the flag and call `scheduleAutoRefresh()` + `resetCountdown()`.
- Manual button already works during throttle (refreshCooldown is the only gate, and it's bounded to 10s).

### 3. Explicit pinch-to-zoom (frontend)

Update Leaflet map init:

```js
const map = L.map("map", {
  zoomControl: true,
  touchZoom: true,
  scrollWheelZoom: true,
}).setView([20, 0], 3);
```

Both options are already `true` by default; setting them explicitly documents intent and guards against accidental regressions.

### 4. Geolocation on first load (frontend)

Replace the bottom of the IIFE:

```js
// ── Boot ──────────────────────────────────────────────────────────────────────
scheduleAutoRefresh();

if (navigator.geolocation) {
  navigator.geolocation.getCurrentPosition(
    pos => {
      map.setView([pos.coords.latitude, pos.coords.longitude], 10);
      // moveend handler triggers the initial fetch at the new location
    },
    () => fetchAndRenderFlights(),
    { timeout: 5000, maximumAge: 60000 }
  );
} else {
  fetchAndRenderFlights();
}
```

### Files touched

| File | Change |
|---|---|
| `app.py` | Add 429 branch before `raise_for_status()` |
| `static/map.js` | Rate-limit handler, pause/resume state, geolocation boot, explicit zoom opts |
| `tests/test_app.py` | Two new tests for `rate_limited` response |

### Test plan (backend)

- 429 from OpenSky → response JSON is `{"error": "rate_limited", "message": ...}`, status 200. No exception raised.
- 429 does **not** trigger token invalidation or retry (that path is 401-only).

Frontend behavior (rate-limit UI, geolocation, pinch) is verified manually in the browser — there is no JS test harness in this repo, so no new automated coverage there.

## Summary

- Throttle becomes a first-class error state: distinct server response, distinct toast, explicit pause of auto-refresh, automatic recovery on next success.
- Geolocation is opt-in via the browser's own permission flow; denial falls back to the current behavior.
- Pinch-to-zoom already works by virtue of Leaflet defaults; we document it with explicit options.
