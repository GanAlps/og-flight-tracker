# Flight Tracker — Task List

---

## Phase 1: Project Setup & Base App ✅

**Task 1** — Initialize project structure
- Create `requirements.txt` with Flask and requests
- Create directory layout: `static/icons/`, `templates/`, `tests/`
- Create empty `app.py`, `static/map.js`, `static/style.css`, `templates/index.html`

**Task 2** — Create Flask app with index route
- `app.py`: Flask app instance, `GET /` route that renders `templates/index.html`
- `templates/index.html`: minimal HTML skeleton (head, body, placeholder div)

**Task 3** — Tests for base app
- `tests/test_app.py`: test `GET /` returns 200 and HTML content-type
- Run full suite, confirm passing with coverage

---

## Phase 2: Backend — Flights Endpoint ✅

**Task 4** — Implement `GET /api/flights` route
- Parse `lat1`, `lon1`, `lat2`, `lon2` query params
- Return 400 JSON error if any param is missing or non-numeric

**Task 5** — Add bounding box zoom guard
- Compute area = `(lat2 - lat1) * (lon2 - lon1)`
- If area > 25, return `{"error": "zoom_required", "message": "Zoom in to see flights."}`

**Task 6** — Integrate OpenSky Network API
- Call `https://opensky-network.org/api/states/all` with `lamin/lomin/lamax/lomax`
- Map raw state vector fields (indices 0,1,2,5,6,7,8,9,10) to normalized flight objects
- Skip entries where `lat` or `lon` is `None`
- Return `{"flights": [...], "count": N, "timestamp": T}`
- On requests exception, return `{"error": "upstream_error", "message": "OpenSky API unavailable."}`

**Task 7** — Add in-memory rate limit cache
- Module-level dict `_cache = {}` and `_last_fetch = 0`
- If a request arrives within 10 seconds of the last fetch, return cached response
- Cache is keyed on the rounded bounding box (1 decimal place) to allow slight pan reuse

**Task 8** — Tests for `/api/flights`
- Test: missing params → 400
- Test: bbox area > 25 → zoom_required error JSON
- Test: OpenSky returns states → normalized flight list (mock `requests.get`)
- Test: OpenSky returns empty states → empty list
- Test: OpenSky raises exception → upstream_error JSON
- Test: second call within 10s returns cached data without calling OpenSky again
- Run full suite with coverage

---

## Phase 3: Backend — Geocoding Endpoint ✅

**Task 9** — Implement `GET /api/geocode` route
- Parse `q` query param; return 400 if missing
- Call Nominatim: `https://nominatim.openstreetmap.org/search?q=...&format=json&limit=1`
- Set `User-Agent` header (Nominatim policy requirement)
- If result found, return `{"lat": ..., "lon": ..., "display_name": ...}`
- If no result, return `{"error": "not_found", "message": "Location not found."}`
- On requests exception, return `{"error": "upstream_error", "message": "Geocoding unavailable."}`

**Task 10** — Tests for `/api/geocode`
- Test: missing `q` → 400
- Test: Nominatim returns results → lat/lon/display_name (mock `requests.get`)
- Test: Nominatim returns empty list → not_found JSON
- Test: Nominatim raises exception → upstream_error JSON
- Run full suite with coverage

---

## Phase 4: Frontend — Map Layout ✅

**Task 11** — Build full-screen map page (`index.html` + `style.css`)
- Load Leaflet CSS and JS from CDN in `<head>`
- Top bar: search input + "Go" button, manual refresh button, status text area
- Map container `<div id="map">` fills remaining viewport height
- `style.css`: flex layout, top bar styling, map fills 100% height

**Task 12** — Initialize Leaflet map (`map.js`)
- Create Leaflet map centered on (20, 0) at zoom 4
- Add OpenStreetMap tile layer
- Export/attach map instance for use by other functions
- Verify map renders correctly in browser

---

## Phase 5: Frontend — Flight Markers & Popups ✅

**Task 13** — Create rotatable plane SVG icon
- `static/icons/plane.svg`: simple airplane outline SVG, viewBox centered at origin
- Icon will be rotated via CSS transform in Leaflet DivIcon

**Task 14** — Implement flight marker rendering
- In `map.js`: `fetchAndRenderFlights()` function
  - Read current map bounds (`map.getBounds()`)
  - Call `GET /api/flights?lat1=&lon1=&lat2=&lon2=`
  - On zoom_required response: show zoom toast, clear markers
  - On upstream_error: show error banner, keep existing markers
  - On success: clear all existing markers, place new Leaflet `DivIcon` markers
  - Each marker: plane SVG rotated to `heading` degrees, blue if airborne, gray if on_ground

**Task 15** — Implement click popup
- Each marker bindPopup with HTML showing: callsign, country, altitude (m), speed (m/s), heading (°), status (Airborne / On Ground)
- Popup styled to match top bar aesthetics

---

## Phase 6: Frontend — Interactivity & UI States ✅

**Task 16** — Auto-refresh with countdown timer
- `setInterval` every 15 000 ms calling `fetchAndRenderFlights()`
- Status bar shows "Refreshing in Xs..." counting down each second with `setInterval` at 1 000 ms
- Resets countdown on each fetch

**Task 17** — Manual refresh button with cooldown
- Clicking refresh button calls `fetchAndRenderFlights()` immediately
- Button disabled for 10 seconds after any fetch (auto or manual); re-enabled after

**Task 18** — Location search
- On "Go" button click or Enter key: call `GET /api/geocode?q=<input value>`
- On success: `map.setView([lat, lon], 8)` then call `fetchAndRenderFlights()`
- On not_found: show toast "Location not found"
- On error: show toast "Geocoding unavailable"

**Task 19** — UI state messages
- Toast helper function: shows a dismissable message bar below the top bar for 4 seconds
- Loading: show spinner overlay on map during any fetch in progress
- Status bar flight count: "24 flights in view" updated after each successful fetch
- "No flights in this area" toast when flights array is empty

---

## Phase 7: README & Polish ✅

**Task 20** — Write `README.md`
- What the app does
- Prerequisites (Python 3.8+)
- Install steps (`pip install -r requirements.txt`)
- Run step (`python app.py`)
- Open browser at `localhost:5000`
- Notes on OpenSky rate limits and anonymous API usage

**Task 21** — Final browser verification
- Start server, open browser
- Confirm: map loads, flights appear, icon rotation matches heading
- Confirm: click popup shows correct fields
- Confirm: auto-refresh countdown works, markers update
- Confirm: search for "London" pans map and loads flights
- Confirm: zoom out fully → zoom_required message appears
- Confirm: status bar shows correct flight count
