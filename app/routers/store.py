"""Cloud-first data endpoints (blueprint §8): personality, preferences, reminders,
meetings and conversation history — all in PostgreSQL, scoped to the user. These
replace the mobile app's local SQLite so the phone stores no personal data."""
from __future__ import annotations

import json
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

import base64
import binascii

from ..auth import current_user
from ..db import get_db
from ..ai.service import embedding_service
from ..models import (
    Conversation,
    Document,
    DocumentChunk,
    Meeting,
    Memory,
    Message,
    Personality,
    Preference,
    Reminder,
    SavedLocation,
    Task,
)
from ..services.documents import chunk_text, extract_text
from ..schemas import (
    ConversationOut,
    DocumentIn,
    DocumentOut,
    MeetingIn,
    MeetingOut,
    MemoryOut,
    MemoryUpdate,
    MessageOut,
    Personality as PersonalitySchema,
    PreferenceIn,
    ReminderIn,
    ReminderOut,
    LocationIn,
    LocationOut,
    TaskIn,
    TaskOut,
)

router = APIRouter()


def _iso(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt else None


# --- Personality ---
@router.get("/api/personality", response_model=PersonalitySchema)
def get_personality(user_id: str = Depends(current_user), db: Session = Depends(get_db)):
    row = db.get(Personality, user_id)
    if row is None:
        return PersonalitySchema()
    try:
        return PersonalitySchema(**json.loads(row.data))
    except Exception:
        return PersonalitySchema()


@router.put("/api/personality", response_model=PersonalitySchema)
def put_personality(
    body: PersonalitySchema, user_id: str = Depends(current_user), db: Session = Depends(get_db)
):
    row = db.get(Personality, user_id)
    if row is None:
        row = Personality(user_id=user_id, data=body.model_dump_json())
        db.add(row)
    else:
        row.data = body.model_dump_json()
    db.commit()
    return body


# --- Preferences ---
@router.get("/api/preferences/{key}")
def get_pref(key: str, user_id: str = Depends(current_user), db: Session = Depends(get_db)):
    row = db.get(Preference, (user_id, key))
    return {"key": key, "value": row.value if row else ""}


@router.put("/api/preferences")
def put_pref(
    body: PreferenceIn, user_id: str = Depends(current_user), db: Session = Depends(get_db)
):
    row = db.get(Preference, (user_id, body.key))
    if row is None:
        db.add(Preference(user_id=user_id, key=body.key, value=body.value))
    else:
        row.value = body.value
    db.commit()
    return {"ok": True}


# --- Memories (view / edit / delete — blueprint V1 §3.4) ---
@router.get("/api/memories", response_model=list[MemoryOut])
def list_memories(user_id: str = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.execute(
        select(Memory).where(Memory.user_id == user_id).order_by(Memory.id.desc())
    ).scalars().all()
    return [
        MemoryOut(id=m.id, type=m.type, category=m.category, value=m.value, createdAt=_iso(m.created_at))
        for m in rows
    ]


@router.patch("/api/memories/{mid}", response_model=MemoryOut)
def update_memory(
    mid: int, body: MemoryUpdate, user_id: str = Depends(current_user), db: Session = Depends(get_db)
):
    m = db.get(Memory, mid)
    if m is None or m.user_id != user_id:
        raise HTTPException(status_code=404, detail="Not found")
    if body.value is not None and body.value.strip():
        m.value = body.value.strip()
        # Re-embed so semantic recall stays accurate after an edit.
        if embedding_service.enabled:
            m.embedding = embedding_service.embed(m.value)
    if body.category is not None:
        m.category = body.category.strip() or None
    db.commit()
    db.refresh(m)
    return MemoryOut(id=m.id, type=m.type, category=m.category, value=m.value, createdAt=_iso(m.created_at))


@router.delete("/api/memories/{mid}")
def delete_memory(mid: int, user_id: str = Depends(current_user), db: Session = Depends(get_db)):
    """Let the user tell the assistant to forget something (blueprint V1 §3.4)."""
    m = db.get(Memory, mid)
    if m and m.user_id == user_id:
        db.delete(m)
        db.commit()
    return {"ok": True}


# --- Reminders ---
@router.get("/api/reminders", response_model=list[ReminderOut])
def list_reminders(user_id: str = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.execute(
        select(Reminder).where(Reminder.user_id == user_id).order_by(Reminder.id.desc())
    ).scalars().all()
    return [
        ReminderOut(id=r.id, text=r.text, dueAt=_iso(r.due_at), done=r.done, createdAt=_iso(r.created_at))
        for r in rows
    ]


@router.post("/api/reminders", response_model=ReminderOut)
def create_reminder(
    body: ReminderIn, user_id: str = Depends(current_user), db: Session = Depends(get_db)
):
    due = None
    if body.dueAt:
        try:
            due = datetime.fromisoformat(body.dueAt.replace("Z", "+00:00"))
        except ValueError:
            due = None
    r = Reminder(user_id=user_id, text=body.text, due_at=due)
    db.add(r)
    db.commit()
    db.refresh(r)
    return ReminderOut(id=r.id, text=r.text, dueAt=_iso(r.due_at), done=r.done, createdAt=_iso(r.created_at))


@router.delete("/api/reminders/{rid}")
def delete_reminder(rid: int, user_id: str = Depends(current_user), db: Session = Depends(get_db)):
    r = db.get(Reminder, rid)
    if r and r.user_id == user_id:
        db.delete(r)
        db.commit()
    return {"ok": True}


# --- Meetings ---
@router.post("/api/meetings", response_model=MeetingOut)
def create_meeting(
    body: MeetingIn, user_id: str = Depends(current_user), db: Session = Depends(get_db)
):
    m = Meeting(
        user_id=user_id,
        title=body.title,
        transcript=body.transcript,
        insights=json.dumps(body.insights) if body.insights is not None else None,
    )
    db.add(m)
    db.commit()
    db.refresh(m)
    return MeetingOut(
        id=m.id, title=m.title or "", transcript=m.transcript or "", insights=body.insights,
        createdAt=_iso(m.created_at),
    )


@router.get("/api/meetings", response_model=list[MeetingOut])
def list_meetings(user_id: str = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.execute(
        select(Meeting).where(Meeting.user_id == user_id).order_by(Meeting.id.desc())
    ).scalars().all()
    out = []
    for m in rows:
        try:
            ins = json.loads(m.insights) if m.insights else None
        except Exception:
            ins = None
        out.append(
            MeetingOut(
                id=m.id, title=m.title or "Meeting", transcript=m.transcript or "",
                insights=ins, createdAt=_iso(m.created_at),
            )
        )
    return out


@router.delete("/api/meetings/{mid}")
def delete_meeting(mid: int, user_id: str = Depends(current_user), db: Session = Depends(get_db)):
    m = db.get(Meeting, mid)
    if m and m.user_id == user_id:
        db.delete(m)
        db.commit()
    return {"ok": True}


# --- Tasks ---
@router.get("/api/tasks", response_model=list[TaskOut])
def list_tasks(user_id: str = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.execute(
        select(Task).where(Task.user_id == user_id).order_by(Task.id.desc())
    ).scalars().all()
    return [
        TaskOut(id=t.id, text=t.text, done=t.done, dueAt=_iso(t.due_at), createdAt=_iso(t.created_at))
        for t in rows
    ]


@router.post("/api/tasks", response_model=TaskOut)
def create_task(body: TaskIn, user_id: str = Depends(current_user), db: Session = Depends(get_db)):
    due = None
    if body.dueAt:
        try:
            due = datetime.fromisoformat(body.dueAt.replace("Z", "+00:00"))
        except ValueError:
            due = None
    t = Task(user_id=user_id, text=body.text, due_at=due)
    db.add(t)
    db.commit()
    db.refresh(t)
    return TaskOut(id=t.id, text=t.text, done=t.done, dueAt=_iso(t.due_at), createdAt=_iso(t.created_at))


@router.patch("/api/tasks/{tid}")
def complete_task(tid: int, user_id: str = Depends(current_user), db: Session = Depends(get_db)):
    t = db.get(Task, tid)
    if t and t.user_id == user_id:
        t.done = True
        db.commit()
    return {"ok": True}


@router.delete("/api/tasks/{tid}")
def delete_task(tid: int, user_id: str = Depends(current_user), db: Session = Depends(get_db)):
    t = db.get(Task, tid)
    if t and t.user_id == user_id:
        db.delete(t)
        db.commit()
    return {"ok": True}


# --- Saved locations (for geofence reminders) ---
def _loc_out(x: SavedLocation) -> LocationOut:
    return LocationOut(
        id=x.id, label=x.label, latitude=x.latitude, longitude=x.longitude,
        radiusM=x.radius_m, createdAt=_iso(x.created_at),
    )


@router.get("/api/locations", response_model=list[LocationOut])
def list_locations(user_id: str = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.execute(
        select(SavedLocation).where(SavedLocation.user_id == user_id).order_by(SavedLocation.id.desc())
    ).scalars().all()
    return [_loc_out(x) for x in rows]


@router.post("/api/locations", response_model=LocationOut)
def create_location(body: LocationIn, user_id: str = Depends(current_user), db: Session = Depends(get_db)):
    x = SavedLocation(
        user_id=user_id, label=body.label, latitude=body.latitude,
        longitude=body.longitude, radius_m=body.radiusM,
    )
    db.add(x)
    db.commit()
    db.refresh(x)
    return _loc_out(x)


@router.delete("/api/locations/{lid}")
def delete_location(lid: int, user_id: str = Depends(current_user), db: Session = Depends(get_db)):
    x = db.get(SavedLocation, lid)
    if x and x.user_id == user_id:
        db.delete(x)
        db.commit()
    return {"ok": True}


# --- Documents (upload photos/files → extract text) ---
@router.post("/api/documents", response_model=DocumentOut)
def upload_document(
    body: DocumentIn, user_id: str = Depends(current_user), db: Session = Depends(get_db)
):
    try:
        data = base64.b64decode(body.dataBase64)
    except (binascii.Error, ValueError):
        raise HTTPException(status_code=400, detail="Invalid file encoding.")
    text = extract_text(body.filename, body.mimeType, data)
    doc = Document(user_id=user_id, filename=body.filename, mimetype=body.mimeType, text=text)
    db.add(doc)
    db.commit()
    db.refresh(doc)

    # RAG pipeline: chunk → embed → store in pgvector for semantic retrieval.
    if text and embedding_service.enabled:
        for ch in chunk_text(text):
            db.add(
                DocumentChunk(
                    document_id=doc.id, user_id=user_id, text=ch, embedding=embedding_service.embed(ch)
                )
            )
        db.commit()

    return DocumentOut(
        id=doc.id, filename=doc.filename, mimetype=doc.mimetype,
        textPreview=(text or "")[:400], createdAt=_iso(doc.created_at),
    )


@router.get("/api/documents", response_model=list[DocumentOut])
def list_documents(user_id: str = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.execute(
        select(Document).where(Document.user_id == user_id).order_by(Document.id.desc())
    ).scalars().all()
    return [
        DocumentOut(
            id=d.id, filename=d.filename, mimetype=d.mimetype,
            textPreview=(d.text or "")[:400], createdAt=_iso(d.created_at),
        )
        for d in rows
    ]


@router.delete("/api/documents/{did}")
def delete_document(did: int, user_id: str = Depends(current_user), db: Session = Depends(get_db)):
    d = db.get(Document, did)
    if d and d.user_id == user_id:
        db.delete(d)
        db.commit()
    return {"ok": True}


# --- Conversations (history for the sidebar) ---
@router.get("/api/conversations", response_model=list[ConversationOut])
def list_conversations(user_id: str = Depends(current_user), db: Session = Depends(get_db)):
    convs = db.execute(
        select(Conversation).where(Conversation.user_id == user_id).order_by(Conversation.id.desc())
    ).scalars().all()
    out = []
    for c in convs:
        last = db.execute(
            select(Message.content)
            .where(Message.conversation_id == c.id)
            .order_by(Message.id.desc())
            .limit(1)
        ).scalar()
        count = db.execute(
            select(func.count(Message.id)).where(Message.conversation_id == c.id)
        ).scalar_one()
        out.append(
            ConversationOut(
                id=c.id, title=c.title or "Chat", createdAt=_iso(c.created_at),
                preview=last or "", messageCount=count,
            )
        )
    return out


@router.delete("/api/conversations/{cid}")
def delete_conversation(cid: int, user_id: str = Depends(current_user), db: Session = Depends(get_db)):
    c = db.get(Conversation, cid)
    if c and c.user_id == user_id:
        db.delete(c)
        db.commit()
    return {"ok": True}


@router.get("/api/conversations/{cid}/messages", response_model=list[MessageOut])
def conversation_messages(
    cid: int, user_id: str = Depends(current_user), db: Session = Depends(get_db)
):
    conv = db.get(Conversation, cid)
    if conv is None or conv.user_id != user_id:
        raise HTTPException(status_code=404, detail="Not found")
    rows = db.execute(
        select(Message).where(Message.conversation_id == cid).order_by(Message.id.asc())
    ).scalars().all()
    return [MessageOut(id=m.id, role=m.role, content=m.content) for m in rows]
