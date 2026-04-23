# UX Polish — Change Details

## Overview

Five small, related UX improvements. All frontend-only (no backend or test changes).

1. Show the "zoom in" toast exactly once on transition into the `zoom_required` state; pause auto-refresh so it doesn't fire again every 15 s. Same treatment applied to `rate_limited` for consistency.
2. Fix: geolocation on first load succeeded but the map stayed on the world view. Root cause: the 5 s timeout is shorter than a first-time OS geolocation acquisition (prompt + GPS warmup), so the error callback fires and we fall back to the default view. Bump timeout, drop high-accuracy requirement.
3. Add a circular "My location" icon button overlaid on the map (bottom-right, Google-Maps-style) that re-runs geolocation and recenters on click.
4. Lower the auto-refresh cadence to 60 s. Any successful fetch (manual, `moveend`, or the 60 s tick itself) resets the interval — so an active, panning user naturally avoids duplicate time-based refreshes.
5. Add a welcome header above the top bar: **"Welcome to Osho's experimental flight tracking website"**.

## Constraints and edge cases

- **Toast-once is transition-triggered.** We track `lastErrorKind` (null | `"zoom_required"` | `"rate_limited"`). Toast fires only when the kind changes. Panning while still zoomed out does not re-toast; zooming in → success → back out → re-toast (state transition).
- **Auto-refresh pause already exists** from the rate-limit change. We generalise: `stopAutoRefresh()` handles both `zoom_required` and `rate_limited`, with the status text reflecting which state we're in.
- **Geolocation timeout bumped to 15 s.** Enough for first-prompt click + OS location acquisition without being annoying on slower devices. `enableHighAccuracy: false` uses network/IP geolocation, resolves in ~1 s for subsequent calls.
- **My location button reuses the geolocation helper.** On error (denied, unavailable, timeout) show a warn toast — "Couldn't get location". Cached position (`maximumAge: 60000`) makes repeat clicks instant.
- **60 s default cadence is only slightly above OpenSky's 10 s per-bbox server-side cap**, so we're within spec. A data point: at 60 s, worst-case 24 hours of continuous viewing = 1,440 state calls, well under any reasonable quota.
- **Interval reset on every fetch** is done by always calling `scheduleAutoRefresh()` at the end of a successful fetch. `setInterval` → replaces the existing handle, effectively resetting the 60 s clock.
- **Title layout.** The new welcome header goes as a sibling row above `#top-bar`, both inside the existing flex-column body. Map still gets `flex: 1`. The two fixed-offset elements (`#toast-container`, `#loading-overlay` at `top: 52px`) need their offsets updated to account for the new title height.

## Solution

### 1. Toast-once + single pause path (static/map.js)

Add:
```js
let lastErrorKind = null;
```

Rewrite the error branches in `fetchAndRenderFlights`:

```js
if (data.error === "zoom_required") {
  clearMarkers();
  if (lastErrorKind !== "zoom_required") {
    showToast("Zoom in to see flights", "warn");
  }
  lastErrorKind = "zoom_required";
  stopAutoRefresh("Zoom in to see flights");
  return;
}

if (data.error === "rate_limited") {
  clearMarkers();
  if (lastErrorKind !== "rate_limited") {
    showToast(data.message || "Rate limited — tap ↺ to retry", "warn");
  }
  lastErrorKind = "rate_limited";
  stopAutoRefresh("Rate limited — tap ↺ to retry");
  return;
}
```

Update `stopAutoRefresh` to accept a status-text override:

```js
function stopAutoRefresh(statusLabel) {
  autoRefreshPaused = true;
  if (autoRefreshTimer) { clearInterval(autoRefreshTimer); autoRefreshTimer = null; }
  if (countdownTimer) { clearInterval(countdownTimer); countdownTimer = null; }
  if (statusLabel) statusText.textContent = statusLabel;
}
```

On successful fetch: set `lastErrorKind = null` (alongside the existing resume logic).

### 2. Geolocation fix (static/map.js)

Boot path:
```js
navigator.geolocation.getCurrentPosition(
  pos => map.setView([pos.coords.latitude, pos.coords.longitude], 10),
  () => fetchAndRenderFlights(),
  { timeout: 15000, maximumAge: 60000, enableHighAccuracy: false }
);
```

### 3. My location icon (templates/index.html, static/map.js, static/style.css)

Floating circular button overlaid on the map in the bottom-right corner, above the Leaflet attribution strip. Inline SVG crosshair icon (center dot + four tick marks), matching the Google-Maps-style affordance.

HTML (as a sibling of `#map`, so it can be absolutely positioned against the body's layout):
```html
<button id="locate-btn" title="My location" aria-label="My location">
  <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
    <circle cx="12" cy="12" r="8"></circle>
    <circle cx="12" cy="12" r="2.5" fill="currentColor" stroke="none"></circle>
    <line x1="12" y1="1.5" x2="12" y2="4.5"></line>
    <line x1="12" y1="19.5" x2="12" y2="22.5"></line>
    <line x1="1.5" y1="12" x2="4.5" y2="12"></line>
    <line x1="19.5" y1="12" x2="22.5" y2="12"></line>
  </svg>
</button>
```

CSS:
```css
#locate-btn {
  position: absolute;
  right: 14px;
  bottom: 28px;           /* clears Leaflet attribution */
  width: 40px;
  height: 40px;
  padding: 0;
  border-radius: 50%;
  background: #16213e;
  color: #e0e0e0;
  border: 1px solid #0f3460;
  box-shadow: 0 2px 6px rgba(0, 0, 0, 0.4);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1200;          /* above Leaflet controls, below toast */
}

#locate-btn:hover:not(:disabled) {
  background: #1f2f55;
  color: #4a90d9;
}
```

JS:
```js
const locateBtn = document.getElementById("locate-btn");
locateBtn.addEventListener("click", () => {
  if (!navigator.geolocation) {
    showToast("Geolocation not supported", "warn");
    return;
  }
  navigator.geolocation.getCurrentPosition(
    pos => map.setView([pos.coords.latitude, pos.coords.longitude], 10),
    err => {
      const msg = err && err.code === 1 ? "Location permission denied" : "Couldn't get location";
      showToast(msg, "warn");
    },
    { timeout: 15000, maximumAge: 60000, enableHighAccuracy: false }
  );
});
```

### 4. 60 s cadence + reset on every fetch (static/map.js)

- `countdownValue` default changes from `15` → `60`.
- `resetCountdown` starts at `60`.
- `scheduleAutoRefresh` interval changes from `15000` → `60000`.
- In `fetchAndRenderFlights`, the existing `startCooldown()` + `resetCountdown()` already happen on every fetch; we also always call `scheduleAutoRefresh()` on success (not only when resuming from pause) so the interval resets. One-line change: move the `scheduleAutoRefresh()` call so it runs unconditionally after a successful render.

### 5. Welcome header (templates/index.html, static/style.css)

HTML: new element just before `#top-bar`:

```html
<header id="site-title">Welcome to Osho's experimental flight tracking website</header>
```

CSS:
```css
#site-title {
  padding: 10px 14px;
  background: #0f3460;
  border-bottom: 1px solid #16213e;
  font-size: 15px;
  font-weight: 600;
  color: #e0e0e0;
  text-align: center;
  flex-shrink: 0;
  z-index: 1001;
}
```

And bump the two fixed-offset elements to clear the new header:
```css
#toast-container { top: 92px; }
#loading-overlay { top: 92px; }
```
(new title ~40 px + existing top bar 52 px = 92 px)

### Files touched

| File | Change |
|---|---|
| `templates/index.html` | Add `#site-title`, add `#locate-btn` |
| `static/map.js` | Toast-once, unified `stopAutoRefresh`, geolocation timeout fix, locate button wiring, 60 s cadence + unconditional reset |
| `static/style.css` | `#site-title` rule, bump `top:` on toast/overlay |

No backend changes, no new tests. Behavior is manual-verified.

## Summary

- "Zoom in" and "Rate limited" become one-shot toasts tied to state transitions; persistent status text covers the steady state.
- Geolocation timeout is increased to cover first-prompt latency, and high-accuracy is dropped for speed.
- Explicit "My location" button gives the user a recovery path if the initial geolocate fell through.
- 60 s refresh cadence with auto-reset on every fetch keeps data fresh for passive viewers while avoiding redundant polls for active ones.
- Welcome header lands above the existing top bar with matched styling.
