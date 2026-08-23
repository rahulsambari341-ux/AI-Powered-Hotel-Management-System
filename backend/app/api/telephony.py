"""
Twilio telephony integration.

Call flow:

    Customer calls hotel
            |
            v
    POST /telephony/incoming
            |
            v
    Greeting + Gather
            |
            v
    POST /telephony/gather
            |
            v
    SpeechResult
            |
            v
    Same conversation engine as /ai/chat
            |
            v
    Ollama/Qwen + booking tools + MySQL
            |
            v
    Kokoro local TTS
            |
            v
    WAV audio
            |
            v
    Redis/in-memory storage
            |
            v
    Twilio <Play>
            |
            v
    Customer hears response
            |
            v
    Gather next turn

IMPORTANT:

Every Twilio webhook should return valid TwiML.

If AI/TTS fails, we fall back to Twilio <Say>
so the phone call does not unexpectedly die.

Phase 9:

- Redis-backed audio cache
- Rate limiting
- Twilio signature validation
"""

import uuid
import logging

from fastapi import APIRouter, Request, Response
from fastapi.responses import Response as RawResponse

from twilio.request_validator import RequestValidator
from twilio.twiml.voice_response import VoiceResponse, Gather

from app.config import settings
from app.agents.conversation import run_turn
from app.services.tts_service import synthesize_speech
from app import storage
from app.rate_limit import limiter


logger = logging.getLogger("telephony")


router = APIRouter(
    prefix="/telephony",
    tags=["telephony"],
)


# ============================================================
# Messages
# ============================================================

GREETING = (
    "Hello! Welcome to ABC Hotel. "
    "I'm your AI booking assistant. "
    "How may I help you today?"
)

NO_SPEECH_PROMPT = (
    "Sorry, I didn't catch that. "
    "Could you say that again?"
)

TROUBLE_PROMPT = (
    "I'm having trouble processing that right now. "
    "Let's try again. How can I help you?"
)

GOODBYE = (
    "Thank you for calling ABC Hotel. Goodbye!"
)


# ============================================================
# Audio storage
# ============================================================

_AUDIO_KEY_PREFIX = "telephony_audio:"


def _cache_audio(
    audio_bytes: bytes,
) -> str:
    """
    Store generated TTS audio using Phase 9 storage.

    Redis is used when configured.

    Otherwise storage.py automatically falls back
    to in-memory storage.
    """

    clip_id = uuid.uuid4().hex

    storage.set_bytes(
        f"{_AUDIO_KEY_PREFIX}{clip_id}",
        audio_bytes,
        ttl_seconds=settings.AUDIO_CACHE_TTL_SECONDS,
    )

    return clip_id


def _play_url(
    clip_id: str,
) -> str:
    """
    Build the public URL Twilio uses to retrieve
    the generated WAV file.
    """

    return (
        f"{settings.PUBLIC_BASE_URL}"
        f"/telephony/audio/{clip_id}.wav"
    )


# ============================================================
# TwiML response helper
# ============================================================

def _twiml_response(
    vr: VoiceResponse,
) -> Response:
    """
    Convert VoiceResponse into an HTTP XML response.
    """

    return Response(
        content=str(vr),
        media_type="application/xml",
    )


# ============================================================
# Twilio request validation
# ============================================================

async def _is_valid_twilio_request(
    request: Request,
) -> bool:
    """
    Verify that the request came from Twilio.

    If TWILIO_AUTH_TOKEN is empty, validation is skipped
    for local development/testing.

    Production must configure TWILIO_AUTH_TOKEN.
    """

    if not settings.TWILIO_AUTH_TOKEN:

        return True

    validator = RequestValidator(
        settings.TWILIO_AUTH_TOKEN
    )

    signature = request.headers.get(
        "X-Twilio-Signature",
        "",
    )

    url = str(request.url)

    form = await request.form()

    return validator.validate(
        url,
        dict(form),
        signature,
    )


# ============================================================
# Gather next turn
# ============================================================

def _gather_next_turn(
    vr: VoiceResponse,
) -> None:
    """
    Ask Twilio to listen for the customer's next sentence.
    """

    gather = Gather(
        input="speech",
        action="/telephony/gather",
        method="POST",
        speech_timeout="auto",
        language="en-IN",
    )

    vr.append(gather)

    # If no speech is received,
    # Twilio reaches this fallback.
    vr.say(GOODBYE)
    vr.hangup()


# ============================================================
# Incoming call
# ============================================================

@router.post("/incoming")
@limiter.limit("60/minute")
async def incoming_call(
    request: Request,
):
    """
    Called by Twilio when a customer calls the hotel.

    1. Validate Twilio request.
    2. Greet customer.
    3. Start speech gathering.
    """

    if not await _is_valid_twilio_request(request):

        return RawResponse(
            content=b"Invalid request signature",
            status_code=403,
        )

    vr = VoiceResponse()

    try:

        gather = Gather(
            input="speech",
            action="/telephony/gather",
            method="POST",
            speech_timeout="auto",
            language="en-IN",
        )

        gather.say(GREETING)

        vr.append(gather)

        vr.say(GOODBYE)
        vr.hangup()

    except Exception:

        logger.exception(
            "Error building greeting TwiML"
        )

        vr = VoiceResponse()

        vr.say(TROUBLE_PROMPT)
        vr.hangup()

    return _twiml_response(vr)


# ============================================================
# Gather customer speech
# ============================================================

@router.post("/gather")
@limiter.limit("60/minute")
async def gather_speech(
    request: Request,
):
    """
    Receive speech from Twilio.

    Twilio sends:

        SpeechResult
        CallSid

    CallSid becomes the conversation session ID.
    """

    if not await _is_valid_twilio_request(request):

        return RawResponse(
            content=b"Invalid request signature",
            status_code=403,
        )

    form = await request.form()

    call_sid = form.get(
        "CallSid",
        "unknown-call",
    )

    speech_text = (
        form.get("SpeechResult") or ""
    ).strip()

    vr = VoiceResponse()

    # ========================================================
    # No speech
    # ========================================================

    if not speech_text:

        gather = Gather(
            input="speech",
            action="/telephony/gather",
            method="POST",
            speech_timeout="auto",
            language="en-IN",
        )

        gather.say(NO_SPEECH_PROMPT)

        vr.append(gather)

        vr.say(GOODBYE)
        vr.hangup()

        return _twiml_response(vr)

    # ========================================================
    # AI conversation
    # ========================================================

    try:

        logger.info(
            "Call %s customer speech: %s",
            call_sid,
            speech_text,
        )

        reply_text = run_turn(
            session_id=call_sid,
            user_message=speech_text,
        )

        logger.info(
            "Call %s AI reply: %s",
            call_sid,
            reply_text,
        )

    except Exception:

        logger.exception(
            "Error running conversation turn "
            "for call %s",
            call_sid,
        )

        gather = Gather(
            input="speech",
            action="/telephony/gather",
            method="POST",
            speech_timeout="auto",
            language="en-IN",
        )

        gather.say(TROUBLE_PROMPT)

        vr.append(gather)

        vr.say(GOODBYE)
        vr.hangup()

        return _twiml_response(vr)

    # ========================================================
    # Kokoro TTS
    # ========================================================

    try:

        logger.info(
            "Generating Kokoro TTS for call %s...",
            call_sid,
        )

        audio_bytes = synthesize_speech(
            reply_text,
        )

        clip_id = _cache_audio(
            audio_bytes,
        )

        audio_url = _play_url(
            clip_id,
        )

        logger.info(
            "Kokoro audio cached for call %s: %s",
            call_sid,
            audio_url,
        )

        vr.play(audio_url)

    except Exception:

        """
        If Kokoro fails, do not kill the phone call.

        Twilio's own Say voice is used as fallback.
        """

        logger.exception(
            "Kokoro TTS failed for call %s. "
            "Falling back to Twilio Say.",
            call_sid,
        )

        vr.say(reply_text)

    # ========================================================
    # Continue conversation
    # ========================================================

    _gather_next_turn(vr)

    return _twiml_response(vr)


# ============================================================
# Serve Kokoro WAV audio
# ============================================================

@router.get("/audio/{clip_id}.wav")
def get_audio_clip(
    clip_id: str,
):
    """
    Serve cached Kokoro WAV audio.

    Audio is consumed once.

    If Twilio never requests the audio,
    Redis/in-memory TTL automatically removes it.
    """

    audio_bytes = storage.pop_bytes(
        f"{_AUDIO_KEY_PREFIX}{clip_id}",
    )

    if audio_bytes is None:

        return RawResponse(
            content=b"",
            media_type="audio/wav",
            status_code=404,
        )

    return RawResponse(
        content=audio_bytes,
        media_type="audio/wav",
        headers={
            "Cache-Control": "no-store",
        },
    )


# ============================================================
# Call status
# ============================================================

@router.post("/status")
async def call_status(
    request: Request,
):
    """
    Receive optional Twilio call status updates.

    Examples:

        ringing
        in-progress
        completed
        failed
    """

    form = await request.form()

    logger.info(
        "Call status update: %s",
        dict(form),
    )

    return {
        "received": True,
    }