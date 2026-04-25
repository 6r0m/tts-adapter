"""Shared pytest fixtures.

`live_client` skips integration tests cleanly when no server is running at
localhost:9880, instead of letting httpx.ConnectError surface as ERROR.

Reserve the bare `httpx.Client` for tests that intentionally exercise the
no-server path (very rare).
"""

import httpx
import pytest

BASE_URL = "http://localhost:9880"


@pytest.fixture
def live_client():
    """HTTP client that requires the main adapter to be running.

    Skips the test (not errors) when the server isn't reachable. Uses
    trust_env=False to avoid the SOCKS proxy trap on dev machines.
    """
    client = httpx.Client(base_url=BASE_URL, timeout=30.0, trust_env=False)
    try:
        client.get("/health")
    except httpx.ConnectError:
        pytest.skip(f"Live server not running at {BASE_URL}")
    return client
