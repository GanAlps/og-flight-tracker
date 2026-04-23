import logging
import os
import time
from collections import OrderedDict

import requests
from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

load_dotenv()

_OPENSKY_CLIENT_ID = os.environ.get("OPENSKY_CLIENT_ID")
_OPENSKY_CLIENT_SECRET = os.environ.get("OPENSKY_CLIENT_SECRET")
if not _OPENSKY_CLIENT_ID or not _OPENSKY_CLIENT_SECRET:
    raise RuntimeError(
        "OPENSKY_CLIENT_ID and OPENSKY_CLIENT_SECRET must be set "
        "(copy .env.example to .env and fill in credentials)."
    )
logging.info(
    "OpenSky credentials loaded (client_id length=%d, secret length=%d)",
    len(_OPENSKY_CLIENT_ID), len(_OPENSKY_CLIENT_SECRET),
)

app = Flask(__name__)

# Per-bbox cache: bbox_key -> (fetch_time, result). OrderedDict so we can
# bound memory with an LRU eviction when running on a long-lived process
# (e.g. a warm Vercel instance). Each entry carries its own fetch_time so a
# recently-fetched bbox can't mask a stale cached entry for a different bbox.
_cache = OrderedDict()
_CACHE_TTL_SECONDS = 10
_CACHE_MAX_ENTRIES = 128
_BBOX_AREA_LIMIT = 25

_TOKEN_URL = "https://auth.opensky-network.org/auth/realms/opensky-network/protocol/openid-connect/token"
_token = None
_token_expires_at = 0
_TOKEN_REFRESH_BUFFER_SECONDS = 30


def _get_token():
    global _token, _token_expires_at
    if _token and time.time() < _token_expires_at - _TOKEN_REFRESH_BUFFER_SECONDS:
        return _token
    reason = "refresh-before-expiry" if _token else "initial"
    app.logger.info("Fetching OpenSky token (reason=%s)", reason)
    try:
        resp = requests.post(
            _TOKEN_URL,
            data={
                "grant_type": "client_credentials",
                "client_id": _OPENSKY_CLIENT_ID,
                "client_secret": _OPENSKY_CLIENT_SECRET,
            },
            timeout=10,
        )
        resp.raise_for_status()
        body = resp.json()
    except Exception:
        app.logger.exception("OpenSky token fetch failed")
        raise
    _token = body["access_token"]
    expires_in = body.get("expires_in", 1800)
    _token_expires_at = time.time() + expires_in
    app.logger.info("OpenSky token acquired (expires_in=%ds)", expires_in)
    return _token


def _invalidate_token(reason="explicit"):
    global _token, _token_expires_at
    if _token:
        app.logger.warning("Invalidating OpenSky token (reason=%s)", reason)
    _token = None
    _token_expires_at = 0


def _call_opensky(lat1, lon1, lat2, lon2, token):
    return requests.get(
        "https://opensky-network.org/api/states/all",
        params={"lamin": lat1, "lomin": lon1, "lamax": lat2, "lomax": lon2},
        headers={"Authorization": f"Bearer {token}"},
        timeout=10,
    )


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/flights")
def get_flights():
    try:
        lat1 = float(request.args["lat1"])
        lon1 = float(request.args["lon1"])
        lat2 = float(request.args["lat2"])
        lon2 = float(request.args["lon2"])
    except (KeyError, ValueError):
        return jsonify({"error": "invalid_params", "message": "lat1, lon1, lat2, lon2 are required numeric params."}), 400

    area = (lat2 - lat1) * (lon2 - lon1)
    if area > _BBOX_AREA_LIMIT:
        app.logger.info("Flight request rejected: bbox area %.2f > %d (zoom_required)", area, _BBOX_AREA_LIMIT)
        return jsonify({"error": "zoom_required", "message": "Zoom in to see flights."})

    bbox_key = (round(lat1, 1), round(lon1, 1), round(lat2, 1), round(lon2, 1))
    now = time.time()

    entry = _cache.get(bbox_key)
    if entry is not None:
        fetch_time, cached_result = entry
        if now - fetch_time < _CACHE_TTL_SECONDS:
            _cache.move_to_end(bbox_key)
            return jsonify(cached_result)

    try:
        token = _get_token()
        resp = _call_opensky(lat1, lon1, lat2, lon2, token)
        if resp.status_code == 401:
            app.logger.warning("/states/all returned 401; refreshing token and retrying once")
            _invalidate_token(reason="states-endpoint-401")
            token = _get_token()
            resp = _call_opensky(lat1, lon1, lat2, lon2, token)
        if resp.status_code == 429:
            app.logger.warning("/states/all returned 429 (rate_limited)")
            return jsonify({
                "error": "rate_limited",
                "message": "OpenSky rate limit reached. Auto-refresh is paused — retry manually.",
            })
        resp.raise_for_status()
        data = resp.json()
    except Exception:
        app.logger.exception("OpenSky /states/all request failed")
        return jsonify({"error": "upstream_error", "message": "OpenSky API unavailable."})

    states = data.get("states") or []
    flights = []
    for s in states:
        lat, lon = s[6], s[5]
        if lat is None or lon is None:
            continue
        flights.append({
            "id": s[0],
            "callsign": (s[1] or "").strip() or "N/A",
            "country": s[2],
            "lat": lat,
            "lon": lon,
            "altitude": s[7],
            "speed": s[9],
            "heading": s[10],
            "on_ground": s[8],
        })

    result = {"flights": flights, "count": len(flights), "timestamp": int(now)}
    _cache[bbox_key] = (now, result)
    _cache.move_to_end(bbox_key)
    while len(_cache) > _CACHE_MAX_ENTRIES:
        _cache.popitem(last=False)
    return jsonify(result)


@app.route("/api/geocode")
def geocode():
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify({"error": "invalid_params", "message": "q param is required."}), 400

    try:
        resp = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": q, "format": "json", "limit": 1},
            headers={"User-Agent": "og-ft-flight-tracker/1.0"},
            timeout=10,
        )
        resp.raise_for_status()
        results = resp.json()
    except Exception:
        app.logger.exception("Nominatim geocode request failed")
        return jsonify({"error": "upstream_error", "message": "Geocoding unavailable."})

    if not results:
        app.logger.info("Geocode no result (q length=%d)", len(q))
        return jsonify({"error": "not_found", "message": "Location not found."})

    r = results[0]
    return jsonify({"lat": float(r["lat"]), "lon": float(r["lon"]), "display_name": r["display_name"]})


@app.route("/api/suggestions")
def suggestions():
    q = request.args.get("q", "").strip()
    if len(q) < 2:
        return jsonify([])

    try:
        resp = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": q, "format": "json", "limit": 5, "addressdetails": 0},
            headers={"User-Agent": "og-ft-flight-tracker/1.0"},
            timeout=10,
        )
        resp.raise_for_status()
        results = resp.json()
    except Exception:
        app.logger.warning("Nominatim suggestions request failed", exc_info=True)
        return jsonify([])

    return jsonify([
        {"display_name": r["display_name"], "lat": float(r["lat"]), "lon": float(r["lon"])}
        for r in results
    ])


if __name__ == "__main__":  # pragma: no cover
    app.run(debug=True, port=5001)
