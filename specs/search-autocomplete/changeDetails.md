# Search Autocomplete — Change Details

## Overview

As the user types in the search bar, show a live dropdown of matching location suggestions (cities, airports, countries) fetched from the Nominatim API. The user can click any suggestion to immediately pan the map there. The existing "Go" button and Enter-key flow remain unchanged.

## Solution

**Backend:** Add a new `GET /api/suggestions?q=<text>` endpoint. It calls Nominatim with `limit=5` and returns a list of `{display_name, lat, lon}` objects. This is kept separate from `/api/geocode` (which returns a single definitive result) to maintain a clear separation of concerns.

**Frontend:** Attach a debounced `input` event listener to the search field (300ms debounce). On each firing, if the query is ≥ 2 characters, fetch `/api/suggestions` and render a dropdown `<ul>` absolutely positioned below the search input. Clicking a suggestion fills the input, closes the dropdown, pans the map, and loads flights — identical to pressing "Go".

**Example backend response:**
```json
[
  {"display_name": "London, England, United Kingdom", "lat": 51.5074, "lon": -0.1278},
  {"display_name": "London, Ontario, Canada",         "lat": 42.9849, "lon": -81.2453}
]
```

**Example CSS positioning:**
```
┌──────────────────────────────────────┐
│ [ lond                          ] [Go]│
│ ┌──────────────────────────────────┐  │
│ │ London, England, United Kingdom  │  │
│ │ London, Ontario, Canada          │  │
│ │ London, Kentucky, United States  │  │
│ └──────────────────────────────────┘  │
└──────────────────────────────────────┘
```

## Edge Cases & Constraints

- **Debounce (300ms):** Do not fire on every keystroke — wait for the user to pause.
- **Minimum 2 chars:** Suppress fetch if query length < 2 to avoid noise.
- **Empty result:** Hide dropdown silently (no toast).
- **Nominatim rate limit:** Nominatim asks for ≤ 1 req/s per user agent. The 300ms debounce, combined with the user typing, naturally stays well within this.
- **Dropdown dismiss:** Close on outside click, on Escape key, and when the input is cleared.
- **Keyboard navigation:** Not required for this change (mouse click selection only).
- **No duplicate cache needed:** Suggestions are ephemeral UX — no server-side caching required.
