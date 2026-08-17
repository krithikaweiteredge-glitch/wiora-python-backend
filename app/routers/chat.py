import logging
import traceback

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import cache

logger = logging.getLogger("wiora.chat")
from ..auth import current_user
from ..db import get_db
from ..orchestrator.chat import handle_chat
from ..schemas import ChatRequest, ChatResponse

router = APIRouter()


@router.post("/api/chat", response_model=ChatResponse)
def chat(
    req: ChatRequest,
    user_id: str = Depends(current_user),
    db: Session = Depends(get_db),
) -> ChatResponse:
    # Per-user rate limit via Redis (no-op if Redis is disabled).
    if not cache.allow_request(user_id):
        raise HTTPException(status_code=429, detail="Too many requests — slow down a moment.")
    try:
        reply, provider, conversation_id, tool_calls, pending = handle_chat(db, user_id, req)
    except Exception as e:  # noqa: BLE001
        msg = str(e)
        # Log the real error so 500s are never invisible.
        logger.error("chat failed: %s\n%s", msg, traceback.format_exc())
        if "429" in msg or "rate limit" in msg.lower():
            wait = ""
            m = __import__("re").search(r"try again in ([\dhms.\s]+?)\.", msg)
            if m:
                wait = f" Try again in ~{m.group(1).strip()}."
            raise HTTPException(
                status_code=429,
                detail=f"Wiora's daily AI limit (free Groq tier) was reached.{wait}",
            )
        raise HTTPException(status_code=500, detail="Something went wrong handling your message.")
    return ChatResponse(
        reply=reply,
        provider=provider,
        conversation_id=conversation_id,
        toolCalls=tool_calls,
        pendingConfirmations=pending,
    )
