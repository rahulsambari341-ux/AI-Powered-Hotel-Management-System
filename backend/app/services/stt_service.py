"""
Speech-to-text service, using faster-whisper (runs locally, no per-request
API cost, good accuracy). Model loads lazily on first use and is cached in
memory afterward, since loading takes a few seconds.

First run downloads the model weights from Hugging Face (a few hundred MB
for the 'base' model) - this needs a real internet connection and only
happens once; after that it's cached on disk.

Phase 8.3 (multilingual): faster-whisper already does language detection
as part of transcription - we don't need a separate step or model. This
module now also returns the detected language code and Whisper's own
confidence score, so the conversation layer can decide whether to trust
it (see LANGUAGE_CONFIDENCE_THRESHOLD below).

Supported languages for this project: English, Hindi, Telugu, Tamil
(en/hi/te/ta). Whisper's 'base' model can detect and transcribe many more
languages than these four, but conversation.py only has a tailored system
prompt for these four - any other detected language currently falls back
to English in the conversation layer rather than pretending to support it.
"""

import tempfile
import os

from faster_whisper import WhisperModel

_model: WhisperModel | None = None

# 'base' balances speed and accuracy well for a receptionist use case.
# Use 'tiny' for faster/lower-accuracy, 'small' or 'medium' for higher accuracy but slower.
MODEL_SIZE = "base"

# Below this confidence, we don't trust the detected language enough to
# switch the conversation's language - short utterances like "yes" or
# "okay" are often ambiguous between languages and shouldn't cause a
# language flip. The caller (conversation.py) keeps using whatever
# language was last established for the session instead.
LANGUAGE_CONFIDENCE_THRESHOLD = 0.6

SUPPORTED_LANGUAGE_CODES = {"en", "hi", "te", "ta"}


def get_model() -> WhisperModel:
    global _model
    if _model is None:
        try:
            _model = WhisperModel(MODEL_SIZE, device="cpu", compute_type="int8")
        except Exception as e:
            raise RuntimeError(
                f"Could not load the Whisper STT model ({e}). "
                "This usually means no internet connection on first run "
                "(model weights need to download from Hugging Face)."
            )
    return _model


def transcribe_audio_bytes(audio_bytes: bytes, filename_hint: str = "audio.wav") -> dict:
    """
    Transcribes raw audio bytes to text. Writes to a temp file because
    faster-whisper's API expects a file path.

    Returns a dict: {"text": str, "language": str | None, "language_confident": bool}
    - "language" is Whisper's detected ISO 639-1 code (e.g. "en", "hi", "te", "ta"),
      or whatever it detected even if unsupported by this project (e.g. "fr") -
      the caller decides what to do with an unsupported code.
    - "language_confident" is False if Whisper's own probability score was
      below LANGUAGE_CONFIDENCE_THRESHOLD - callers should not switch the
      conversation's language based on a low-confidence detection.
    """
    model = get_model()
    suffix = os.path.splitext(filename_hint)[1] or ".wav"

    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(audio_bytes)
        tmp_path = tmp.name

    try:
        segments, info = model.transcribe(
            tmp_path, 
            beam_size=5,
            initial_prompt="ABC Hotel, room booking, check-in, check-out, Deluxe, Standard, Premium, Suite, parking, wifi, 2026, 2027, 2028, 2029"
        )
        text = " ".join(segment.text.strip() for segment in segments)
        language = getattr(info, "language", None)
        language_probability = getattr(info, "language_probability", 0.0) or 0.0
        return {
            "text": text.strip(),
            "language": language,
            "language_confident": language_probability >= LANGUAGE_CONFIDENCE_THRESHOLD,
        }
    finally:
        os.remove(tmp_path)
