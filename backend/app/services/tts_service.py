"""
Local Text-to-Speech service using Kokoro.

Phase 8/9 compatible TTS implementation.

Kokoro runs locally, so OPENAI_API_KEY is NOT required for TTS.

Public interface intentionally remains:

    synthesize_speech(text, voice)

This keeps the existing voice.py and telephony.py architecture
compatible with the rest of the project.
"""

import io
import logging

import numpy as np
import soundfile as sf
from kokoro import KPipeline


logger = logging.getLogger("tts_service")


# ============================================================
# Kokoro Configuration
# ============================================================

KOKORO_REPO_ID = "hexgrad/Kokoro-82M"

# Default Kokoro English voice.
DEFAULT_VOICE = "af_heart"

# Kokoro English pipeline.
_pipeline: KPipeline | None = None


# ============================================================
# Load Kokoro Pipeline
# ============================================================

def get_tts_pipeline() -> KPipeline:
    """
    Lazily create the Kokoro TTS pipeline.

    The model is loaded only when TTS is used for the first time.
    """

    global _pipeline

    if _pipeline is None:

        logger.info("Loading Kokoro TTS model...")

        _pipeline = KPipeline(
            lang_code="a",
            repo_id=KOKORO_REPO_ID,
        )

        logger.info("Kokoro TTS model loaded successfully.")

    return _pipeline


# ============================================================
# Generate Speech
# ============================================================

def synthesize_speech(
    text: str,
    voice: str = DEFAULT_VOICE,
) -> bytes:
    """
    Convert text into WAV audio bytes using local Kokoro TTS.

    Parameters
    ----------
    text:
        Text that should be spoken.

    voice:
        Kokoro voice name.

    Returns
    -------
    bytes:
        Generated WAV audio bytes.

    Raises
    ------
    RuntimeError:
        If TTS generation fails.
    """

    if not text or not text.strip():
        raise RuntimeError("TTS text cannot be empty.")

    try:

        pipeline = get_tts_pipeline()

        logger.info(
            "Generating Kokoro speech using voice '%s'...",
            voice,
        )

        audio_chunks = []

        generator = pipeline(
            text.strip(),
            voice=voice,
            speed=1.0,
            split_pattern=r"\n+",
        )

        for _, _, audio in generator:

            audio_chunks.append(audio)

        if not audio_chunks:
            raise RuntimeError(
                "Kokoro generated no audio."
            )

        # Combine all generated chunks.
        audio_data = np.concatenate(audio_chunks)

        # Write WAV directly into memory.
        audio_buffer = io.BytesIO()

        sf.write(
            audio_buffer,
            audio_data,
            24000,
            format="WAV",
        )

        audio_buffer.seek(0)

        audio_bytes = audio_buffer.read()

        logger.info(
            "Kokoro speech generated successfully (%d bytes).",
            len(audio_bytes),
        )

        return audio_bytes

    except Exception as e:

        logger.exception(
            "Kokoro TTS generation failed."
        )

        raise RuntimeError(
            f"Kokoro TTS generation failed: {str(e)}"
        ) from e
