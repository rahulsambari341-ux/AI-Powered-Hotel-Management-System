"""
Voice API.

POST /voice/transcribe
    Audio file -> speech text + detected language

POST /voice/synthesize
    Text -> Kokoro WAV audio

Phase 8:
    Multilingual STT/language detection.

Phase 9:
    Rate limiting and production-safe API behavior.

TTS:
    Local Kokoro TTS.

OPENAI_API_KEY is NOT required for TTS.
"""

import io

from fastapi import (
    APIRouter,
    UploadFile,
    File,
    HTTPException,
    Request,
)
from fastapi.responses import StreamingResponse

from app.schemas.voice import (
    TranscribeResponse,
    SynthesizeRequest,
)

from app.services.stt_service import (
    transcribe_audio_bytes,
)

from app.services.tts_service import (
    synthesize_speech,
)

from app.rate_limit import limiter


router = APIRouter(
    prefix="/voice",
    tags=["voice"],
)


# ============================================================
# Configuration
# ============================================================

MAX_AUDIO_SIZE_BYTES = 25 * 1024 * 1024

DEFAULT_VOICE = "af_heart"


# ============================================================
# POST /voice/transcribe
# ============================================================

@router.post(
    "/transcribe",
    response_model=TranscribeResponse,
)
@limiter.limit("30/minute")
async def transcribe(
    request: Request,
    file: UploadFile = File(...),
):
    """
    Receive an audio file and convert it into text.

    Flow:

        Audio
          ↓
        Faster-Whisper
          ↓
        Text + language information
    """

    audio_bytes = await file.read()

    # --------------------------------------------------------
    # Validate uploaded audio
    # --------------------------------------------------------

    if not audio_bytes:

        raise HTTPException(
            status_code=422,
            detail="Uploaded audio file is empty",
        )

    if len(audio_bytes) > MAX_AUDIO_SIZE_BYTES:

        raise HTTPException(
            status_code=413,
            detail="Audio file too large (max 25MB)",
        )

    # --------------------------------------------------------
    # Speech-to-text
    # --------------------------------------------------------

    try:

        result = transcribe_audio_bytes(
            audio_bytes,
            filename_hint=file.filename or "audio.wav",
        )

    except RuntimeError as e:

        raise HTTPException(
            status_code=503,
            detail=str(e),
        )

    # --------------------------------------------------------
    # Phase 8 multilingual STT result
    # --------------------------------------------------------

    if isinstance(result, dict):

        text = result.get("text", "")

        language = result.get(
            "language",
            "unknown",
        )

        language_confident = result.get(
            "language_confident",
            False,
        )

    else:

        # Backward compatibility in case an older
        # STT implementation returns only a string.

        text = result

        language = "unknown"

        language_confident = False

    # --------------------------------------------------------
    # Make sure speech was detected
    # --------------------------------------------------------

    if not text or not text.strip():

        raise HTTPException(
            status_code=422,
            detail="Could not detect any speech in the audio",
        )

    return TranscribeResponse(
        text=text,
        language=language,
        language_confident=language_confident,
    )


# ============================================================
# POST /voice/synthesize
# ============================================================

@router.post("/synthesize")
@limiter.limit("30/minute")
def synthesize(
    request: Request,
    payload: SynthesizeRequest,
):
    """
    Convert text into speech using local Kokoro TTS.

    Input:

        {
            "text": "...",
            "voice": "af_heart"
        }

    Output:

        WAV audio stream.

    No OpenAI API key is required.
    """

    # --------------------------------------------------------
    # Validate text
    # --------------------------------------------------------

    if not payload.text or not payload.text.strip():

        raise HTTPException(
            status_code=422,
            detail="text must not be empty",
        )

    # --------------------------------------------------------
    # Voice
    # --------------------------------------------------------

    voice = (
        payload.voice
        if payload.voice
        else DEFAULT_VOICE
    )

    # --------------------------------------------------------
    # Kokoro TTS
    # --------------------------------------------------------

    try:

        audio_bytes = synthesize_speech(
            payload.text,
            voice=voice,
        )

    except RuntimeError as e:

        raise HTTPException(
            status_code=503,
            detail=str(e),
        )

    # --------------------------------------------------------
    # Return WAV audio
    # --------------------------------------------------------

    return StreamingResponse(
        io.BytesIO(audio_bytes),
        media_type="audio/wav",
        headers={
            "Content-Disposition": (
                "inline; filename=tts_output.wav"
            ),
            "Cache-Control": "no-store",
        },
    )