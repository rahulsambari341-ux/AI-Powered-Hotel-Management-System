"""
POST /ai/chat

Text-based endpoint for talking to the AI booking agent. This is the same
conversation engine that Phase 5/6 will feed with transcribed speech - by
building this as a plain text endpoint first, we can fully test the AI's
behavior before voice is anywhere in the picture.
"""

from fastapi import APIRouter, HTTPException, Request

from app.schemas.chat import ChatRequest, ChatResponse
from app.agents.conversation import run_turn
from app.rate_limit import limiter

router = APIRouter(prefix="/ai", tags=["ai"])


@router.post("/chat", response_model=ChatResponse)
@limiter.limit("20/minute")
def chat(request: Request, payload: ChatRequest):
    try:
        reply = run_turn(payload.session_id, payload.message, detected_language=payload.detected_language)
    except RuntimeError as e:
        # Raised by llm_client when OPENAI_API_KEY is missing - surface a clear message.
        raise HTTPException(status_code=503, detail=str(e))
    return ChatResponse(session_id=payload.session_id, reply=reply)
