"""
Rate limiting tests (Phase 9.4). Unlike every other test file, these
explicitly RE-ENABLE rate limiting (conftest.py disables it globally by
default, since other tests fire many rapid requests and shouldn't be
flaky depending on execution speed/order).

Uses a fresh TestClient + fresh Limiter/app import per test via importlib
reload, so each test starts with a clean rate-limit counter rather than
inheriting hits from earlier tests in this file.
"""

import os
import importlib

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def rate_limited_client():
    """
    Builds a fresh app instance with rate limiting ON, isolated from the
    rest of the test suite's RATE_LIMIT_ENABLED=false setting.
    """
    os.environ["RATE_LIMIT_ENABLED"] = "true"

    import app.config
    importlib.reload(app.config)
    import app.rate_limit
    importlib.reload(app.rate_limit)
    import app.api.chat
    importlib.reload(app.api.chat)
    import app.main
    importlib.reload(app.main)

    client = TestClient(app.main.app)
    yield client

    # Always restore the suite-wide default afterward so later test files
    # aren't affected by this test's monkeying with rate limiting.
    os.environ["RATE_LIMIT_ENABLED"] = "false"
    importlib.reload(app.config)
    importlib.reload(app.rate_limit)
    importlib.reload(app.api.chat)
    importlib.reload(app.main)


def test_chat_endpoint_enforces_rate_limit(rate_limited_client):
    """/ai/chat is limited to 20/minute - the 21st rapid request from the
    same client should be rejected with 429."""
    from unittest.mock import patch
    from app.agents.llm_client import LLMReply

    with patch("app.agents.conversation.call_llm") as mock_llm:
        mock_llm.return_value = LLMReply(content="ok", tool_calls=[])

        statuses = []
        for i in range(22):
            res = rate_limited_client.post("/ai/chat", json={"session_id": f"ratelimit-{i}", "message": "hi"})
            statuses.append(res.status_code)

    assert 200 in statuses, "Some requests should succeed"
    assert 429 in statuses, "Excess requests should be rate-limited"
    # The first 20 should succeed, the 21st+ should be limited (same client/IP)
    assert statuses[:20] == [200] * 20
    assert statuses[20] == 429


def test_rate_limit_response_is_clean_not_a_crash(rate_limited_client):
    """A 429 should be a proper JSON error response, not an unhandled exception."""
    from unittest.mock import patch
    from app.agents.llm_client import LLMReply

    with patch("app.agents.conversation.call_llm") as mock_llm:
        mock_llm.return_value = LLMReply(content="ok", tool_calls=[])
        for i in range(21):
            res = rate_limited_client.post("/ai/chat", json={"session_id": f"ratelimit-b-{i}", "message": "hi"})

    assert res.status_code == 429
    assert res.headers["content-type"].startswith("application/json")
