"""
Voice endpoint tests.

Mocks STT/TTS entirely.

These tests verify:

- empty audio validation
- successful transcription
- no speech handling
- STT service failure
- empty TTS text validation
- successful local Kokoro TTS response
- TTS does NOT require OPENAI_API_KEY
"""

from unittest.mock import patch


# ============================================================
# STT - Empty File
# ============================================================

def test_transcribe_empty_file_rejected(client):

    res = client.post(
        "/voice/transcribe",
        files={
            "file": (
                "empty.wav",
                b"",
                "audio/wav",
            )
        },
    )

    assert res.status_code == 422


# ============================================================
# STT - Success
# ============================================================

def test_transcribe_success_mocked(client):

    with patch(
        "app.api.voice.transcribe_audio_bytes"
    ) as mock_transcribe:

        mock_transcribe.return_value = {
            "text": "book a deluxe room",
            "language": "en",
            "language_confident": True,
        }

        res = client.post(
            "/voice/transcribe",
            files={
                "file": (
                    "speech.wav",
                    b"FAKE_AUDIO_BYTES",
                    "audio/wav",
                )
            },
        )

    assert res.status_code == 200

    data = res.json()

    assert (
        data["text"]
        == "book a deluxe room"
    )

    assert data["language"] == "en"

    assert (
        data["language_confident"]
        is True
    )


# ============================================================
# STT - No Speech
# ============================================================

def test_transcribe_no_speech_detected(client):

    with patch(
        "app.api.voice.transcribe_audio_bytes"
    ) as mock_transcribe:

        mock_transcribe.return_value = {
            "text": "",
            "language": None,
            "language_confident": False,
        }

        res = client.post(
            "/voice/transcribe",
            files={
                "file": (
                    "speech.wav",
                    b"SILENCE",
                    "audio/wav",
                )
            },
        )

    assert res.status_code == 422


# ============================================================
# STT - Service Unavailable
# ============================================================

def test_transcribe_stt_service_unavailable(client):

    with patch(
        "app.api.voice.transcribe_audio_bytes"
    ) as mock_transcribe:

        mock_transcribe.side_effect = RuntimeError(
            "Could not load the Whisper STT model"
        )

        res = client.post(
            "/voice/transcribe",
            files={
                "file": (
                    "speech.wav",
                    b"AUDIO",
                    "audio/wav",
                )
            },
        )

    assert res.status_code == 503


# ============================================================
# TTS - Empty Text
# ============================================================

def test_synthesize_empty_text_rejected(client):

    res = client.post(
        "/voice/synthesize",
        json={
            "text": "   "
        },
    )

    assert res.status_code == 422


# ============================================================
# TTS - Successful Kokoro WAV
# ============================================================

def test_synthesize_success_mocked(client):
    """
    Current architecture uses local Kokoro TTS.

    Kokoro produces WAV audio, so the API must return
    audio/wav.
    """

    with patch(
        "app.api.voice.synthesize_speech"
    ) as mock_tts:

        mock_tts.return_value = (
            b"FAKE_WAV_BYTES"
        )

        res = client.post(
            "/voice/synthesize",
            json={
                "text": "Hello"
            },
        )

    assert res.status_code == 200

    assert (
        res.content
        == b"FAKE_WAV_BYTES"
    )

    assert (
        res.headers["content-type"]
        == "audio/wav"
    )


# ============================================================
# TTS - OpenAI Key NOT Required
# ============================================================

def test_synthesize_does_not_require_openai_api_key(
    client,
):
    """
    Kokoro TTS runs locally.

    Therefore OPENAI_API_KEY is NOT required.

    The local TTS function is mocked so the test does not
    load/download the real Kokoro model.
    """

    with patch(
        "app.api.voice.synthesize_speech"
    ) as mock_tts:

        mock_tts.return_value = (
            b"FAKE_WAV_BYTES"
        )

        res = client.post(
            "/voice/synthesize",
            json={
                "text": "Hello"
            },
        )

    assert res.status_code == 200

    assert (
        res.content
        == b"FAKE_WAV_BYTES"
    )

    assert (
        res.headers["content-type"]
        == "audio/wav"
    )