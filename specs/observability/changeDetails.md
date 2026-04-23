# Observability — Change Details

## Overview

Add structured logging to the Python backend (primary target, since it runs on Vercel where the only observability is stdout/stderr logs) and light console-logging to the frontend. Goal: every failure path logs enough context to diagnose without redeploying. Zero behavior change — HTTP responses and business logic are untouched.

## Constraints

- **No secrets in logs.** Never log `_OPENSKY_CLIENT_ID`, `_OPENSKY_CLIENT_SECRET`, or bearer-token strings. Log lengths or "present/absent" only.
- **No log spam at production cadence.** At 60 s auto-refresh, a chatty app quickly drowns Vercel logs. Reserve INFO for interesting events (token fetch, state transitions, degraded paths) — don't double-log every successful response since Vercel already emits an HTTP access log line per request.
- **Tracebacks on every caught exception.** Use `app.logger.exception(...)` inside every `except` — that is what prints `Traceback (most recent call last):` in Vercel.
- **Same module-level state caveat as before.** Vercel serverless means each cold start is a fresh process, so logs like "new token fetched" will recur on every cold start. That's expected and useful, not a bug.
- **Tests stay quiet.** Tests don't assert on log output; pytest's log capture will silently absorb INFO during test runs.
- **Backward compatibility.** Responses, status codes, error shapes — all unchanged. A reader diffing only logging lines should find no functional change.

## Solution

### Logger configuration (`app.py` startup)

Once at import time, before defining `app`:

```python
import logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
```

Use `app.logger` inside handlers (Flask wires it to the root logger). For the top-level startup message (credential check), the root logger is fine since `app` isn't constructed yet at that point.

After the credential check passes, log one concise line confirming config was loaded:

```python
logging.info(
    "OpenSky credentials loaded (client_id length=%d, secret length=%d)",
    len(_OPENSKY_CLIENT_ID), len(_OPENSKY_CLIENT_SECRET),
)
```

(Length-only so you can spot the whitespace-paste bug without leaking the value.)

### Token layer (`_get_token`, `_invalidate_token`)

- Cache hit: no log (high frequency).
- Cache miss → fetching new token: `INFO` with reason ("initial" vs "refresh-before-expiry").
- Fetch success: `INFO` with `expires_in` (seconds), no token value.
- Fetch failure: `ERROR` with `app.logger.exception` — the caller re-raises, but we want the traceback at the innermost layer so the Vercel log pinpoints auth vs states.
- `_invalidate_token`: `WARNING` with the reason passed by caller (so a 401-triggered invalidate is distinguishable from a natural expiry).

Sketch:
```python
def _get_token():
    global _token, _token_expires_at
    if _token and time.time() < _token_expires_at - _TOKEN_REFRESH_BUFFER_SECONDS:
        return _token
    reason = "refresh-before-expiry" if _token else "initial"
    app.logger.info("Fetching OpenSky token (%s)", reason)
    try:
        resp = requests.post(_TOKEN_URL, data={...}, timeout=10)
        resp.raise_for_status()
        body = resp.json()
    except Exception:
        app.logger.exception("OpenSky token fetch failed")
        raise
    _token = body["access_token"]
    _token_expires_at = time.time() + body.get("expires_in", 1800)
    app.logger.info("OpenSky token acquired (expires_in=%ds)", body.get("expires_in", 1800))
    return _token


def _invalidate_token(reason="explicit"):
    global _token, _token_expires_at
    if _token:
        app.logger.warning("Invalidating OpenSky token (reason=%s)", reason)
    _token = None
    _token_expires_at = 0
```

Call site for 401: `_invalidate_token(reason="states-endpoint-401")`.

### `/api/flights`

- Bbox area over limit → `INFO`: `Flight request rejected: bbox area %f > %d (zoom_required)`.
- Cache hit → no log (high frequency).
- OpenSky 401 → `WARNING`: `/states/all returned 401; refreshing token and retrying`.
- OpenSky 429 → `WARNING`: `/states/all returned 429 (rate_limited)`.
- Any exception in the request/parse pipeline → `ERROR` via `app.logger.exception("OpenSky /states/all request failed")`; return the existing `upstream_error` JSON.
- Success → no log (Vercel access log already records this).

### `/api/geocode`

- Not found → `INFO`: `Geocode no result for q of length %d` (don't log the query itself — could be a location the user considers private).
- Upstream exception → `ERROR` via `app.logger.exception("Nominatim geocode request failed")`.
- Success → no log.

### `/api/suggestions`

- Upstream exception → `WARNING` via `app.logger.exception("Nominatim suggestions request failed")`. (Warning, not error, because the contract is "always return `[]` on failure" — the degraded state is expected and non-fatal.)
- Empty/too-short query → no log.
- Success → no log.

### Frontend (`static/map.js`) — lighter touch

- `fetchAndRenderFlights` catch block: `console.error("fetchAndRenderFlights failed", err)` in addition to the existing `showToast`.
- State transitions: `console.info("Rate-limited; pausing auto-refresh")`, `console.info("Auto-refresh resumed after success")`, `console.info("Zoom-required; pausing auto-refresh")`.
- Geolocation: `console.info` on success with coarse precision, `console.warn` on error with the `PositionError.code`.

Browser DevTools "Preserve log" across navigations picks these up. Useful when reproducing a bug locally.

### Files touched

| File | Change |
|---|---|
| `app.py` | `basicConfig`, startup credential-loaded log, token-layer logs, per-route logs in all three handlers |
| `static/map.js` | `console.error` on fetch catch, `console.info/warn` on state transitions and geolocation |
| `CLAUDE.md` | Add a one-paragraph "Logging" section describing the convention |

### Test plan

- Backend tests already pass; no behavior change. Re-run the 33-test suite with coverage ≥99 % to confirm no regression.
- No new tests added: we don't assert log output. Adding log-content assertions would coupling tests to wording; not worth it at this scale.
- Manual verification on Vercel: reproduce the current "OpenSky API unavailable" error, then inspect the Vercel log — there should be an `ERROR OpenSky /states/all request failed` line with a traceback.

## Summary

- Every `except Exception` in `app.py` now logs a traceback before returning the generic error JSON, so the next Vercel failure shows up as a real stack trace.
- Token lifecycle is visible (fetch, success with expiry, invalidate with reason) without ever printing the secret material or the token string itself.
- Frontend state transitions are mirrored to the browser console so debugging locally doesn't require sprinkling `console.log` each time.
- Nothing logs query strings, credentials, or tokens — only lengths, timings, and reasons.
