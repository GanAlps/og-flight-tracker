import json
import subprocess
import sys
import time
from unittest.mock import MagicMock, patch

import pytest

import app as app_module
from app import app


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


# ── Startup: missing credentials ──────────────────────────────────────────────

def test_app_import_fails_without_credentials(tmp_path):
    """Importing app with creds unset must raise RuntimeError."""
    env = {
        "PATH": "/usr/bin:/bin",
        "HOME": str(tmp_path),
        "PYTHONPATH": str(app_module.__file__).rsplit("/", 1)[0],
    }
    result = subprocess.run(
        [sys.executable, "-c", "import app"],
        env=env, capture_output=True, text=True, cwd=str(tmp_path),
    )
    assert result.returncode != 0
    assert "OPENSKY_CLIENT_ID" in result.stderr


# ── Phase 1: index route ──────────────────────────────────────────────────────

def test_index_returns_200(client):
    resp = client.get("/")
    assert resp.status_code == 200


def test_index_content_type_html(client):
    resp = client.get("/")
    assert "text/html" in resp.content_type


# ── Token layer: _get_token / _invalidate_token ───────────────────────────────

def _mock_token_response(access_token="new_token", expires_in=1800):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"access_token": access_token, "expires_in": expires_in}
    mock_resp.raise_for_status = MagicMock()
    return mock_resp


@patch("app.requests.post")
def test_get_token_fetches_when_cache_empty(mock_post):
    app_module._invalidate_token()
    mock_post.return_value = _mock_token_response(access_token="fresh_token")

    token = app_module._get_token()

    assert token == "fresh_token"
    assert mock_post.call_count == 1
    args, kwargs = mock_post.call_args
    assert args[0] == app_module._TOKEN_URL
    assert kwargs["data"]["grant_type"] == "client_credentials"
    assert kwargs["data"]["client_id"] == "test_client_id"
    assert kwargs["data"]["client_secret"] == "test_client_secret"


@patch("app.requests.post")
def test_get_token_reuses_cached_token_within_expiry(mock_post):
    # Fixture already pre-seeds a valid token; no POST should happen.
    token = app_module._get_token()
    assert token == "test_token"
    assert mock_post.call_count == 0


@patch("app.requests.post")
def test_get_token_refreshes_when_expired(mock_post):
    app_module._token = "old_token"
    app_module._token_expires_at = time.time() - 1  # already expired
    mock_post.return_value = _mock_token_response(access_token="refreshed_token")

    token = app_module._get_token()

    assert token == "refreshed_token"
    assert mock_post.call_count == 1


@patch("app.requests.post")
def test_get_token_propagates_upstream_failure(mock_post):
    app_module._invalidate_token()
    mock_post.side_effect = Exception("network down")

    with pytest.raises(Exception, match="network down"):
        app_module._get_token()


# ── Phase 2: /api/flights ─────────────────────────────────────────────────────

def test_flights_missing_params_returns_400(client):
    resp = client.get("/api/flights")
    assert resp.status_code == 400
    data = json.loads(resp.data)
    assert data["error"] == "invalid_params"


def test_flights_non_numeric_params_returns_400(client):
    resp = client.get("/api/flights?lat1=a&lon1=0&lat2=1&lon2=1")
    assert resp.status_code == 400


def test_flights_zoom_required_when_bbox_too_large(client):
    # area = (60 - 0) * (60 - 0) = 3600 > 25
    resp = client.get("/api/flights?lat1=0&lon1=0&lat2=60&lon2=60")
    data = json.loads(resp.data)
    assert data["error"] == "zoom_required"


def _make_opensky_state(icao="abc123", callsign="UAL123", country="United States",
                         lon=-122.0, lat=37.0, altitude=10000.0,
                         on_ground=False, speed=250.0, heading=270.0):
    # OpenSky state vector: indices 0-10 are the fields we care about
    return [icao, callsign, country, None, None, lon, lat, altitude, on_ground, speed, heading]


@patch("app.requests.get")
def test_flights_returns_normalized_flights(mock_get, client):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"states": [_make_opensky_state()]}
    mock_resp.raise_for_status = MagicMock()
    mock_get.return_value = mock_resp

    resp = client.get("/api/flights?lat1=35&lon1=-125&lat2=40&lon2=-120")
    assert resp.status_code == 200
    data = json.loads(resp.data)
    assert data["count"] == 1
    flight = data["flights"][0]
    assert flight["id"] == "abc123"
    assert flight["callsign"] == "UAL123"
    assert flight["country"] == "United States"
    assert flight["lat"] == 37.0
    assert flight["lon"] == -122.0
    assert flight["altitude"] == 10000.0
    assert flight["speed"] == 250.0
    assert flight["heading"] == 270.0
    assert flight["on_ground"] is False


@patch("app.requests.get")
def test_flights_skips_entries_with_null_position(mock_get, client):
    state_with_null = _make_opensky_state()
    state_with_null[6] = None  # lat is None
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"states": [state_with_null]}
    mock_resp.raise_for_status = MagicMock()
    mock_get.return_value = mock_resp

    resp = client.get("/api/flights?lat1=35&lon1=-125&lat2=40&lon2=-120")
    data = json.loads(resp.data)
    assert data["count"] == 0


@patch("app.requests.get")
def test_flights_empty_states_returns_empty_list(mock_get, client):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"states": None}
    mock_resp.raise_for_status = MagicMock()
    mock_get.return_value = mock_resp

    resp = client.get("/api/flights?lat1=35&lon1=-125&lat2=40&lon2=-120")
    data = json.loads(resp.data)
    assert data["count"] == 0
    assert data["flights"] == []


@patch("app.requests.get")
def test_flights_upstream_exception_returns_error(mock_get, client):
    mock_get.side_effect = Exception("network error")

    resp = client.get("/api/flights?lat1=35&lon1=-125&lat2=40&lon2=-120")
    data = json.loads(resp.data)
    assert data["error"] == "upstream_error"


@patch("app.requests.get")
def test_flights_cache_returns_without_second_api_call(mock_get, client):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"states": [_make_opensky_state()]}
    mock_resp.raise_for_status = MagicMock()
    mock_get.return_value = mock_resp

    url = "/api/flights?lat1=35&lon1=-125&lat2=40&lon2=-120"
    client.get(url)
    client.get(url)

    assert mock_get.call_count == 1


@patch("app.requests.get")
def test_flights_cache_expires_after_rate_limit(mock_get, client):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"states": [_make_opensky_state()]}
    mock_resp.raise_for_status = MagicMock()
    mock_get.return_value = mock_resp

    url = "/api/flights?lat1=35&lon1=-125&lat2=40&lon2=-120"
    client.get(url)

    # Simulate time passing beyond rate limit
    app_module._last_fetch = time.time() - 11

    client.get(url)
    assert mock_get.call_count == 2


# ── Bearer header + 401 retry ─────────────────────────────────────────────────

@patch("app.requests.get")
def test_flights_sends_bearer_header(mock_get, client):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"states": [_make_opensky_state()]}
    mock_resp.raise_for_status = MagicMock()
    mock_get.return_value = mock_resp

    client.get("/api/flights?lat1=35&lon1=-125&lat2=40&lon2=-120")

    _, kwargs = mock_get.call_args
    assert kwargs["headers"]["Authorization"] == "Bearer test_token"


@patch("app.requests.post")
@patch("app.requests.get")
def test_flights_retries_once_on_401(mock_get, mock_post, client):
    unauthorized = MagicMock()
    unauthorized.status_code = 401

    success = MagicMock()
    success.status_code = 200
    success.json.return_value = {"states": [_make_opensky_state()]}
    success.raise_for_status = MagicMock()

    mock_get.side_effect = [unauthorized, success]
    mock_post.return_value = _mock_token_response(access_token="refreshed_after_401")

    resp = client.get("/api/flights?lat1=35&lon1=-125&lat2=40&lon2=-120")

    assert resp.status_code == 200
    data = json.loads(resp.data)
    assert data["count"] == 1
    assert mock_get.call_count == 2
    assert mock_post.call_count == 1
    # Second GET used the refreshed bearer.
    _, second_kwargs = mock_get.call_args_list[1]
    assert second_kwargs["headers"]["Authorization"] == "Bearer refreshed_after_401"


@patch("app.requests.post")
@patch("app.requests.get")
def test_flights_second_401_returns_upstream_error(mock_get, mock_post, client):
    unauthorized = MagicMock()
    unauthorized.status_code = 401
    unauthorized.raise_for_status.side_effect = Exception("401 Unauthorized")

    mock_get.return_value = unauthorized
    mock_post.return_value = _mock_token_response(access_token="still_bad")

    resp = client.get("/api/flights?lat1=35&lon1=-125&lat2=40&lon2=-120")
    data = json.loads(resp.data)
    assert data["error"] == "upstream_error"
    assert mock_get.call_count == 2


# ── Rate-limited (429) branch ─────────────────────────────────────────────────

@patch("app.requests.get")
def test_flights_429_returns_rate_limited(mock_get, client):
    throttled = MagicMock()
    throttled.status_code = 429
    mock_get.return_value = throttled

    resp = client.get("/api/flights?lat1=35&lon1=-125&lat2=40&lon2=-120")
    assert resp.status_code == 200
    data = json.loads(resp.data)
    assert data["error"] == "rate_limited"
    assert "rate limit" in data["message"].lower()


@patch("app.requests.post")
@patch("app.requests.get")
def test_flights_429_does_not_invalidate_token(mock_get, mock_post, client):
    throttled = MagicMock()
    throttled.status_code = 429
    mock_get.return_value = throttled

    client.get("/api/flights?lat1=35&lon1=-125&lat2=40&lon2=-120")

    # Token was pre-seeded; 429 must not trigger a re-fetch via the token endpoint.
    assert mock_post.call_count == 0
    assert app_module._token == "test_token"


# ── Phase 3: /api/geocode ─────────────────────────────────────────────────────

def test_geocode_missing_q_returns_400(client):
    resp = client.get("/api/geocode")
    assert resp.status_code == 400
    data = json.loads(resp.data)
    assert data["error"] == "invalid_params"


def test_geocode_empty_q_returns_400(client):
    resp = client.get("/api/geocode?q=")
    assert resp.status_code == 400


@patch("app.requests.get")
def test_geocode_returns_lat_lon(mock_get, client):
    mock_resp = MagicMock()
    mock_resp.json.return_value = [{"lat": "51.5074", "lon": "-0.1278", "display_name": "London, England"}]
    mock_resp.raise_for_status = MagicMock()
    mock_get.return_value = mock_resp

    resp = client.get("/api/geocode?q=London")
    assert resp.status_code == 200
    data = json.loads(resp.data)
    assert data["lat"] == 51.5074
    assert data["lon"] == -0.1278
    assert "London" in data["display_name"]


@patch("app.requests.get")
def test_geocode_not_found_returns_error(mock_get, client):
    mock_resp = MagicMock()
    mock_resp.json.return_value = []
    mock_resp.raise_for_status = MagicMock()
    mock_get.return_value = mock_resp

    resp = client.get("/api/geocode?q=xyznonexistentplace99999")
    data = json.loads(resp.data)
    assert data["error"] == "not_found"


@patch("app.requests.get")
def test_geocode_upstream_exception_returns_error(mock_get, client):
    mock_get.side_effect = Exception("timeout")

    resp = client.get("/api/geocode?q=London")
    data = json.loads(resp.data)
    assert data["error"] == "upstream_error"


# ── Search autocomplete: /api/suggestions ─────────────────────────────────────

def test_suggestions_missing_q_returns_empty(client):
    resp = client.get("/api/suggestions")
    assert resp.status_code == 200
    assert json.loads(resp.data) == []


def test_suggestions_short_q_returns_empty(client):
    resp = client.get("/api/suggestions?q=L")
    assert json.loads(resp.data) == []


@patch("app.requests.get")
def test_suggestions_returns_mapped_list(mock_get, client):
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = [
        {"display_name": "London, England, United Kingdom", "lat": "51.5074", "lon": "-0.1278"},
        {"display_name": "London, Ontario, Canada", "lat": "42.9849", "lon": "-81.2453"},
    ]
    mock_get.return_value = mock_resp

    resp = client.get("/api/suggestions?q=London")
    data = json.loads(resp.data)
    assert len(data) == 2
    assert data[0]["display_name"] == "London, England, United Kingdom"
    assert data[0]["lat"] == 51.5074
    assert data[0]["lon"] == -0.1278


@patch("app.requests.get")
def test_suggestions_empty_result_returns_empty(mock_get, client):
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = []
    mock_get.return_value = mock_resp

    resp = client.get("/api/suggestions?q=xyzabc")
    assert json.loads(resp.data) == []


@patch("app.requests.get")
def test_suggestions_upstream_exception_returns_empty(mock_get, client):
    mock_get.side_effect = Exception("network error")

    resp = client.get("/api/suggestions?q=London")
    assert json.loads(resp.data) == []
