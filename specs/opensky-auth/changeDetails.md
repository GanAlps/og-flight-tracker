# OpenSky Auth — Change Details

## Overview

Authenticate the `/api/flights` upstream call to OpenSky using OAuth2 client-credentials so the app gets higher rate limits than the anonymous tier. Credentials are read from environment variables (loaded from a local `.env` file in development, from Vercel project settings in production) and never committed to git. The backend obtains a bearer token from OpenSky's auth endpoint, caches it until expiry, and attaches it to every `/states/all` request.

**Out of scope:** Authenticating the Nominatim endpoints (`/api/geocode`, `/api/suggestions`) — Nominatim does not use OAuth2 and the anonymous tier is sufficient.

## Constraints and edge cases

- **Hard fail on missing credentials.** If `OPENSKY_CLIENT_ID` or `OPENSKY_CLIENT_SECRET` is unset at import time, `app.py` raises `RuntimeError` and exits. No anonymous fallback. On Vercel this makes a misconfigured deploy loudly crash on the first invocation instead of silently running degraded.
- **Token lifetime is 30 min.** Cache `(token, expires_at)` in module-level state alongside the existing `_cache` / `_last_fetch`. Refresh when `now >= expires_at - 30s` (small buffer to avoid racing the expiry).
- **Mid-flight expiry.** If `/states/all` returns 401, invalidate the cached token, fetch a new one, retry the request **once**. A second 401 means bad credentials — surface as `upstream_error`.
- **Token endpoint failure** (network error, wrong creds → 400/401) is reported as `upstream_error`, same shape the frontend already handles.
- **Serverless cold starts (Vercel).** The module-level token cache doesn't persist across cold invocations; each cold start fetches a fresh token. Acceptable — token fetch is one extra ~100ms call, and within a warm instance it's reused for the full 30 min. Document as a known limitation; no code change.
- **Secrets never reach the browser.** OAuth happens entirely server-side; the frontend continues to call `/api/flights` with no change.
- **Leak recovery.** If `.env` is ever accidentally committed, rotation is done in OpenSky's account portal — no code change needed.

## Solution

### Files touched

| File | Change |
|---|---|
| `requirements.txt` | Add `python-dotenv==1.0.1` |
| `app.py` | Load `.env`, add token fetch/cache, attach bearer header, 401-retry |
| `.gitignore` | Create; ignore `.env`, `__pycache__`, `.coverage`, `.pytest_cache` |
| `.env.example` | New; template with empty `OPENSKY_CLIENT_ID=` / `OPENSKY_CLIENT_SECRET=` |
| `README.md` | Add "OpenSky credentials (optional)" setup section |
| `tests/test_app.py` | New tests for token fetch, reuse, expiry, 401 retry, anonymous fallback |

### Backend shape (sketch, not final code)

```python
# app.py — top
import os
from dotenv import load_dotenv
load_dotenv()  # no-op in prod (Vercel injects env directly)

_OPENSKY_CLIENT_ID = os.environ.get("OPENSKY_CLIENT_ID")
_OPENSKY_CLIENT_SECRET = os.environ.get("OPENSKY_CLIENT_SECRET")
if not _OPENSKY_CLIENT_ID or not _OPENSKY_CLIENT_SECRET:
    raise RuntimeError(
        "OPENSKY_CLIENT_ID and OPENSKY_CLIENT_SECRET must be set "
        "(see .env.example)."
    )

_TOKEN_URL = "https://auth.opensky-network.org/auth/realms/opensky-network/protocol/openid-connect/token"

_token = None          # str | None
_token_expires_at = 0  # unix seconds

def _get_token():
    """Return a valid bearer token, fetching/refreshing as needed.
    Raises on upstream failure so the caller can map to upstream_error."""
    global _token, _token_expires_at
    if _token and time.time() < _token_expires_at - 30:
        return _token
    resp = requests.post(_TOKEN_URL, data={
        "grant_type": "client_credentials",
        "client_id": _OPENSKY_CLIENT_ID,
        "client_secret": _OPENSKY_CLIENT_SECRET,
    }, timeout=10)
    resp.raise_for_status()
    body = resp.json()
    _token = body["access_token"]
    _token_expires_at = time.time() + body.get("expires_in", 1800)
    return _token
```

The `/api/flights` handler becomes:

```python
def _call_opensky(lat1, lon1, lat2, lon2, token):
    return requests.get(
        "https://opensky-network.org/api/states/all",
        params={"lamin": lat1, "lomin": lon1, "lamax": lat2, "lomax": lon2},
        headers={"Authorization": f"Bearer {token}"},
        timeout=10,
    )

try:
    token = _get_token()
    resp = _call_opensky(lat1, lon1, lat2, lon2, token)
    if resp.status_code == 401:
        _invalidate_token()
        token = _get_token()
        resp = _call_opensky(lat1, lon1, lat2, lon2, token)
    resp.raise_for_status()
    data = resp.json()
except Exception:
    return jsonify({"error": "upstream_error", "message": "OpenSky API unavailable."})
```

### `.env.example`

```
OPENSKY_CLIENT_ID=
OPENSKY_CLIENT_SECRET=
```

### Test plan

All tests continue to mock `app.requests.get` / `app.requests.post`; no network.

Tests need creds present at import. Add `tests/conftest.py` that sets `OPENSKY_CLIENT_ID` / `OPENSKY_CLIENT_SECRET` to dummy values before `app` is imported, so the import-time check passes.

- Missing creds: in a subprocess (or via `importlib.reload` with vars cleared), importing `app` raises `RuntimeError`. One test, isolated so it doesn't break the rest of the suite.
- Token fetch: single POST to `_TOKEN_URL` on first flight call, `Authorization: Bearer <token>` on the states call.
- Token reuse: two flight calls within 30 min → exactly one token POST.
- Token refresh: simulate `_token_expires_at` in the past → second flight call triggers a second token POST.
- 401 retry: first `/states/all` call returns 401 → invalidate token, fetch new token, retry once; success returns normal flight data.
- 401 retry exhausted: second `/states/all` also 401 → `upstream_error`.
- Token endpoint failure → `upstream_error`, no state call made.

A new `reset_token` autouse fixture clears `_token` / `_token_expires_at` between tests, parallel to the existing `reset_cache`.

## Summary

- Secrets enter the process via env vars only; `.env` is local-only and gitignored; Vercel injects prod values directly.
- Missing credentials are a hard startup failure — no silent anonymous degradation. A fresh clone must copy `.env.example` to `.env` and fill in real creds before `python app.py` will start.
- Token caching and 401 retry keep the auth overhead invisible in steady state; cold-start token refetches on Vercel are an accepted cost.
- No frontend change; no change to response shapes.
