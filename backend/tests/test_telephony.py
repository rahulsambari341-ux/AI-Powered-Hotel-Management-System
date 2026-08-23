"""
Telephony (Twilio) tests.

Focus:

Every webhook response must be valid TwiML with a 200 status,
even when AI/TTS layers fail completely.

LLM/TTS are mocked.

These tests also verify:

- audio cache one-time consumption
- Twilio signature validation
- graceful AI failure
- graceful TTS failure
"""

from unittest.mock import patch

import xml.etree.ElementTree as ET

from app.agents.llm_client import LLMReply


# ============================================================
# TwiML Validation Helper
# ============================================================

def _assert_valid_twiml(
    response_text: str,
):
    """
    Raises if the response body isn't valid XML.
    """

    root = ET.fromstring(
        response_text
    )

    assert root.tag == "Response"


# ============================================================
# Incoming Call
# ============================================================

def test_incoming_call_returns_valid_twiml(client):

    res = client.post(
        "/telephony/incoming",
        data={
            "CallSid": "CAtest1",
            "From": "+911234567890",
        },
    )

    assert res.status_code == 200

    _assert_valid_twiml(
        res.text
    )

    assert (
        "Welcome to ABC Hotel"
        in res.text
    )


# ============================================================
# No Speech
# ============================================================

def test_gather_no_speech_returns_valid_twiml(
    client,
):

    res = client.post(
        "/telephony/gather",
        data={
            "CallSid": "CAtest2",
            "SpeechResult": "",
        },
    )

    assert res.status_code == 200

    _assert_valid_twiml(
        res.text
    )

    assert (
        "didn"
        in res.text.lower()
    )


# ============================================================
# Speech -> Conversation Engine
# ============================================================

def test_gather_with_speech_calls_conversation_engine(
    client,
):

    with patch(
        "app.api.telephony.run_turn"
    ) as mock_run_turn, patch(
        "app.api.telephony.synthesize_speech"
    ) as mock_tts:

        mock_run_turn.return_value = (
            "Sure, let me check that for you."
        )

        mock_tts.return_value = (
            b"FAKE_WAV"
        )

        res = client.post(
            "/telephony/gather",
            data={
                "CallSid": "CAtest3",
                "SpeechResult": (
                    "I want to book a room"
                ),
            },
        )

    assert res.status_code == 200

    _assert_valid_twiml(
        res.text
    )

    mock_run_turn.assert_called_once()

    call_kwargs = (
        mock_run_turn
        .call_args
        .kwargs
    )

    assert (
        call_kwargs["session_id"]
        == "CAtest3"
    )

    assert (
        call_kwargs["user_message"]
        == "I want to book a room"
    )


# ============================================================
# AI Failure
# ============================================================

def test_gather_ai_failure_still_returns_valid_twiml(
    client,
):
    """
    CRITICAL reliability test.

    If the AI layer fails, the phone call must still receive
    a graceful valid TwiML response.
    """

    with patch(
        "app.api.telephony.run_turn"
    ) as mock_run_turn:

        mock_run_turn.side_effect = RuntimeError(
            "LLM provider unreachable"
        )

        res = client.post(
            "/telephony/gather",
            data={
                "CallSid": "CAtest4",
                "SpeechResult": "book a room",
            },
        )

    assert res.status_code == 200

    _assert_valid_twiml(
        res.text
    )

    assert (
        "trouble"
        in res.text.lower()
    )


# ============================================================
# TTS Failure -> Twilio Say
# ============================================================

def test_gather_tts_failure_falls_back_to_say(
    client,
):
    """
    If local Kokoro TTS fails, the reply must still be spoken
    through Twilio's own <Say>.
    """

    with patch(
        "app.api.telephony.run_turn"
    ) as mock_run_turn, patch(
        "app.api.telephony.synthesize_speech"
    ) as mock_tts:

        mock_run_turn.return_value = (
            "Your room is confirmed."
        )

        mock_tts.side_effect = RuntimeError(
            "Kokoro TTS failed"
        )

        res = client.post(
            "/telephony/gather",
            data={
                "CallSid": "CAtest5",
                "SpeechResult": (
                    "confirm my booking"
                ),
            },
        )

    assert res.status_code == 200

    _assert_valid_twiml(
        res.text
    )

    assert (
        "Your room is confirmed."
        in res.text
    )


# ============================================================
# Audio Not Found
# ============================================================

def test_audio_clip_not_found_returns_404(
    client,
):

    res = client.get(
        "/telephony/audio/"
        "nonexistent-clip-id.mp3"
    )

    assert res.status_code == 404


# ============================================================
# Audio Cache - One Time Fetch
# ============================================================

def test_audio_clip_served_once_then_expires(
    client,
):
    """
    Confirms the storage-backed audio cache behaves as
    a one-time fetch.

    Current telephony API serves WAV audio.
    """

    from app.api.telephony import (
        _cache_audio,
    )

    clip_id = _cache_audio(
        b"FAKE_AUDIO_CONTENT"
    )

    # --------------------------------------------------------
    # First request -> audio exists
    # --------------------------------------------------------

    res1 = client.get(
        f"/telephony/audio/{clip_id}.wav"
    )

    assert res1.status_code == 200

    assert (
        res1.content
        == b"FAKE_AUDIO_CONTENT"
    )

    # --------------------------------------------------------
    # Second request -> audio consumed
    # --------------------------------------------------------

    res2 = client.get(
        f"/telephony/audio/{clip_id}.wav"
    )

    assert res2.status_code == 404


# ============================================================
# Call Status
# ============================================================

def test_call_status_webhook(client):

    res = client.post(
        "/telephony/status",
        data={
            "CallSid": "CAtest6",
            "CallStatus": "completed",
        },
    )

    assert res.status_code == 200

    assert (
        res.json()["received"]
        is True
    )


# ============================================================
# Twilio Signature Validation
# ============================================================

def test_signature_validation_rejects_missing_signature():

    import os
    import importlib

    os.environ[
        "TWILIO_AUTH_TOKEN"
    ] = "test_auth_token_12345"

    try:

        import app.config
        import app.rate_limit
        import app.api.telephony
        import app.main

        importlib.reload(
            app.config
        )

        importlib.reload(
            app.rate_limit
        )

        importlib.reload(
            app.api.telephony
        )

        importlib.reload(
            app.main
        )

        from fastapi.testclient import (
            TestClient,
        )

        c = TestClient(
            app.main.app
        )

        res = c.post(
            "/telephony/incoming",
            data={
                "CallSid": "CAsig1"
            },
        )

        assert res.status_code == 403

    finally:

        os.environ[
            "TWILIO_AUTH_TOKEN"
        ] = ""

        importlib.reload(
            app.config
        )

        importlib.reload(
            app.rate_limit
        )

        importlib.reload(
            app.api.telephony
        )

        importlib.reload(
            app.main
        )


# ============================================================
# Wrong Signature
# ============================================================

def test_signature_validation_rejects_wrong_signature():

    import os
    import importlib

    os.environ[
        "TWILIO_AUTH_TOKEN"
    ] = "test_auth_token_12345"

    try:

        import app.config
        import app.rate_limit
        import app.api.telephony
        import app.main

        importlib.reload(
            app.config
        )

        importlib.reload(
            app.rate_limit
        )

        importlib.reload(
            app.api.telephony
        )

        importlib.reload(
            app.main
        )

        from fastapi.testclient import (
            TestClient,
        )

        c = TestClient(
            app.main.app
        )

        res = c.post(
            "/telephony/incoming",
            data={
                "CallSid": "CAsig2"
            },
            headers={
                "X-Twilio-Signature": "wrong"
            },
        )

        assert res.status_code == 403

    finally:

        os.environ[
            "TWILIO_AUTH_TOKEN"
        ] = ""

        importlib.reload(
            app.config
        )

        importlib.reload(
            app.rate_limit
        )

        importlib.reload(
            app.api.telephony
        )

        importlib.reload(
            app.main
        )


# ============================================================
# Correct Signature
# ============================================================

def test_signature_validation_accepts_correct_signature():

    import os
    import importlib

    os.environ[
        "TWILIO_AUTH_TOKEN"
    ] = "test_auth_token_12345"

    try:

        import app.config
        import app.rate_limit
        import app.api.telephony
        import app.main

        importlib.reload(
            app.config
        )

        importlib.reload(
            app.rate_limit
        )

        importlib.reload(
            app.api.telephony
        )

        importlib.reload(
            app.main
        )

        from fastapi.testclient import (
            TestClient,
        )

        from twilio.request_validator import (
            RequestValidator,
        )

        c = TestClient(
            app.main.app
        )

        validator = RequestValidator(
            "test_auth_token_12345"
        )

        params = {
            "CallSid": "CAsig3"
        }

        sig = validator.compute_signature(
            "http://testserver/telephony/incoming",
            params,
        )

        res = c.post(
            "/telephony/incoming",
            data=params,
            headers={
                "X-Twilio-Signature": sig
            },
        )

        assert res.status_code == 200

    finally:

        os.environ[
            "TWILIO_AUTH_TOKEN"
        ] = ""

        importlib.reload(
            app.config
        )

        importlib.reload(
            app.rate_limit
        )

        importlib.reload(
            app.api.telephony
        )

        importlib.reload(
            app.main
        )


# ============================================================
# Signature Validation Disabled
# ============================================================

def test_signature_validation_disabled_when_no_auth_token_configured(
    client,
):
    """
    With TWILIO_AUTH_TOKEN unset, local development/testing
    requests do not require a signature.
    """

    res = client.post(
        "/telephony/incoming",
        data={
            "CallSid": "CAsig4"
        },
    )

    assert res.status_code == 200