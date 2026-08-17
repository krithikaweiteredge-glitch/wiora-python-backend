"""Approval endpoint (blueprint §22): the phone calls this AFTER the user approves
a sensitive action (send_email, cancel_calendar_event, ...). We re-validate and
execute the tool server-side, then audit it."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import audit
from ..auth import current_user
from ..db import get_db
from ..schemas import ConfirmToolRequest
from ..tools.base import ToolContext
from ..tools.registry import execute_backend, validate_call

router = APIRouter()


@router.post("/api/tool/confirm")
def confirm_tool(
    req: ConfirmToolRequest,
    user_id: str = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict:
    valid = validate_call(req.name, req.args)
    if valid is None or valid.runs_on != "backend":
        raise HTTPException(status_code=400, detail="Unknown or invalid tool.")
    ctx = ToolContext(
        db=db, user_id=user_id, google_access_token=req.googleAccessToken, timezone=req.timezone
    )
    result = execute_backend(valid, ctx)
    audit.record(db, user_id, "tool_confirm", f"{valid.name}: {result[:120]}")
    return {"result": result}
