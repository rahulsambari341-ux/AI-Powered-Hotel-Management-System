from pydantic import BaseModel


class TranscribeResponse(BaseModel):
    text: str
    # Phase 8.3 (multilingual): detected language code (e.g. "en", "hi",
    # "te", "ta"), or another ISO 639-1 code if Whisper detected a language
    # outside this project's four supported ones. None only if detection
    # somehow failed. Existing consumers (Phase 6 frontend) that only read
    # `text` are unaffected - this is a new, optional-to-use field.
    language: str | None = None
    language_confident: bool = True


class SynthesizeRequest(BaseModel):
    text: str
    voice: str | None = None
