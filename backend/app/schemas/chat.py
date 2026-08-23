from pydantic import BaseModel


class ChatRequest(BaseModel):
    session_id: str
    message: str
    # Phase 8.3 (multilingual): optional ISO 639-1 language hint from STT
    # (e.g. "en", "hi", "te", "ta"). Existing callers that omit this field
    # are unaffected - the conversation just keeps using English or
    # whatever language was previously established for the session.
    detected_language: str | None = None


class ChatResponse(BaseModel):
    session_id: str
    reply: str
