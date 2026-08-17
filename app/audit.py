"""Approval & Audit Engine (blueprint §22): record what the AI did. Approval
gating for high-risk tool actions is added with the Tool Engine in later versions."""
from sqlalchemy.orm import Session

from .models import AuditLog


def record(db: Session, user_id: str, action: str, detail: str | None = None) -> None:
    db.add(AuditLog(user_id=user_id, action=action, detail=detail))
    db.commit()
