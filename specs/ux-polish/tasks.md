# UX Polish — Tasks

All frontend-only. No backend tests change; verification is manual in the browser.

## Phase 1 — Toast-once + unified pause

- [x] **1.1** Added `lastErrorKind` module state.
- [x] **1.2** `stopAutoRefresh(statusLabel)` accepts an override label.
- [x] **1.3** `zoom_required` / `rate_limited` branches only toast on kind transition; both now call `stopAutoRefresh(<label>)`.
- [x] **1.4** Successful fetch resets `lastErrorKind = null`.

## Phase 2 — Geolocation fix

- [x] **2.1** Boot path options: `timeout: 15000, maximumAge: 60000, enableHighAccuracy: false`.

## Phase 3 — My location icon button

- [x] **3.1** `index.html`: `#locate-btn` with inline crosshair SVG, placed as a map sibling.
- [x] **3.2** `style.css`: circular 40 px, bottom-right @ 28 px, above Leaflet attribution, themed hover.
- [x] **3.3** `map.js`: click handler geolocates and `setView`s; warn toast on error.

## Phase 4 — 60 s cadence + reset on every fetch

- [x] **4.1** `countdownValue` default / `resetCountdown` start → `60`.
- [x] **4.2** `scheduleAutoRefresh` interval → `60000`.
- [x] **4.3** `scheduleAutoRefresh()` now runs after every successful fetch (not just on pause-resume), so manual/moveend fetches reset the 60 s clock.

## Phase 5 — Welcome header

- [x] **5.1** `index.html`: `<header id="site-title">…</header>` before `#top-bar`.
- [x] **5.2** `style.css`: `#site-title` rule added; `#toast-container` and `#loading-overlay` `top:` bumped to 92 px.

## Phase 6 — Manual verification (user)

- [ ] **6.1** Reload: welcome header visible, map centers on user location (or shows toast if denied).
- [ ] **6.2** Zoom out → one "Zoom in" toast; pan without zooming in → no repeat toast; zoom in → auto-refresh resumes.
- [ ] **6.3** Locate icon: click recenters map; click with permission denied shows warn toast.
- [ ] **6.4** Steady-state cadence feels like ~60 s between automatic refreshes.
