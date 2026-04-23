# Search Autocomplete — Task List

## Phase 1: Backend — Suggestions Endpoint ✅

**Task 1** — Implement `GET /api/suggestions` route
- Parse `q` param; return `[]` if missing or < 2 chars
- Call Nominatim with `limit=5`, `addressdetails=0`
- Return list of `{display_name, lat, lon}`
- On exception, return `[]` (silent fail — dropdown just stays empty)

**Task 2** — Tests for `/api/suggestions`
- Test: missing `q` → empty list `[]`
- Test: `q` < 2 chars → empty list `[]`
- Test: Nominatim returns results → mapped list
- Test: Nominatim returns empty → `[]`
- Test: Nominatim raises exception → `[]`
- Run full suite with coverage

---

## Phase 2: Frontend — Autocomplete Dropdown ✅

**Task 3** — Add dropdown CSS (`style.css`)
- `.suggestions-dropdown`: absolute, full width of search group, dark theme matching top bar
- `.suggestion-item`: padding, hover highlight, cursor pointer
- `.suggestion-item .primary`: bold location name
- `.suggestion-item .secondary`: smaller, muted country/region suffix

**Task 4** — Implement autocomplete in `map.js`
- Create `<ul id="suggestions-list">` in DOM, positioned below search input
- Debounce `input` event on `search-input` (300ms)
- On fire: if `q.length < 2` hide dropdown; else fetch `/api/suggestions?q=...`
- Render results as `<li>` items; click fills input, closes dropdown, calls `doSearch()`
- Dismiss on: outside click, Escape key, input cleared
