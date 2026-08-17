"""Agent endpoint (blueprint §6 / V4): plan → execute steps → evaluate → track.
`is_multi_step` exposes Intent Detection so the caller can route simple requests
to /api/chat and complex goals here."""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..agent.intent import is_agentic
from ..agent.runner import run_agent
from ..auth import current_user
from ..db import get_db
from ..schemas import AgentRunRequest
from ..tools.base import ToolContext

router = APIRouter()


@router.post("/api/agent/run")
def agent_run(
    req: AgentRunRequest,
    user_id: str = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict:
    now = req.clientNow or datetime.now(timezone.utc).isoformat()
    if req.timezone:
        now = f"{now} ({req.timezone})"
    ctx = ToolContext(
        db=db, user_id=user_id, google_access_token=req.googleAccessToken, timezone=req.timezone
    )
    try:
        return run_agent(db, user_id, req.goal, ctx, now)
    except Exception as e:  # noqa: BLE001
        if "429" in str(e) or "rate limit" in str(e).lower():
            raise HTTPException(status_code=429, detail="Daily AI limit reached — try again later.")
        raise HTTPException(status_code=500, detail="Agent run failed.")


@router.get("/api/agent/is-multi-step")
def is_multi_step(goal: str) -> dict:
    """Intent Detection helper: is this goal worth an agent run?"""
    return {"agentic": is_agentic(goal)}
