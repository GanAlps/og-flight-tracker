import os
import time

os.environ.setdefault("OPENSKY_CLIENT_ID", "test_client_id")
os.environ.setdefault("OPENSKY_CLIENT_SECRET", "test_client_secret")

import pytest

import app as app_module


@pytest.fixture(autouse=True)
def reset_app_state():
    app_module._cache.clear()
    app_module._last_fetch = 0
    app_module._token = "test_token"
    app_module._token_expires_at = time.time() + 3600
    yield
    app_module._cache.clear()
    app_module._last_fetch = 0
    app_module._token = None
    app_module._token_expires_at = 0
