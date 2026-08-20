"""AI Orchestrator (blueprint §6/§22): assemble context → AIService (with tools)
→ run backend tools in a loop, collect device tools for the phone → persist +
audit. A lightweight custom state machine (blueprint's recommended starting point;
LangGraph/Temporal later)."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

import base64
import json

from .. import audit
from ..ai.service import ai_service
from ..memory.engine import build_context_block, retrieve
from ..models import Conversation, Message, Personality as PersonalityRow
from ..schemas import ChatRequest, Personality, ToolCallOut
from ..tools.base import ToolContext
from ..tools.registry import execute_backend, tool_specs, validate_call

MAX_TOOL_LOOPS = 4

TOOL_POLICY = "\n".join(
    [
        "Tool policy:",
        "- Answer with text unless the request clearly needs an ACTION.",
        "- Call save_memory when the user asks to remember something or states a durable fact"
        " about themselves (name/role/company). Never call it to ANSWER a question — reply in words.",
        "- Call create_reminder only when the user asks to be reminded.",
        "- Email: search_email to find, read_email to open. To WRITE an email: if the user says "
        "'draft'/'write', use create_email_draft; if the user says 'send', use send_email (which "
        "asks the user to confirm before it actually sends). Never claim an email was sent unless "
        "send_email was used and confirmed.",
        "- Calendar: get_calendar_events / find_free_time / create_calendar_event. Compute ISO"
        " timeMin/timeMax from the current date-time.",
        "- If a tool reports Gmail/Calendar isn't connected, tell the user to connect it in"
        " Settings; do not retry.",
        "- Call search_web for current facts/news/prices the user asks about that aren't in"
        " the conversation or their own data. Don't use it for personal/stored info.",
        "- Location: save_location stores a named place; create_location_reminder makes a"
        " geofence reminder (\"remind me when I'm near X\"). If the user names a saved place,"
        " call list_locations first to get its coordinates, then pass them along.",
    ]
)


def _summarize(name: str, args: dict) -> str:
    if name == "send_email":
        subj = args.get("subject") or "(no subject)"
        return f'Send email to {args.get("to", "?")} — "{subj}"'
    if name == "cancel_calendar_event":
        return "Cancel a calendar event"
    if name == "update_calendar_event":
        return "Update a calendar event"
    return name


def _build_system_prompt(p: Personality, now: str, memory_block: str) -> str:
    parts = [
        f"You are {p.name}, a personal AI phone assistant.",
        f"Tone: {p.tone}. Formality: {p.formality}. Warmth: {p.warmth}. Confidence: {p.confidence}.",
        f"Keep responses {p.responseLength.lower()}. Humor: {p.humor}. Proactivity: {p.proactivity}.",
        "You help with email, calendar, reminders, contacts, meetings and general questions.",
        "Never claim to have completed an action you cannot yet perform.",
        f"Current date-time: {now}.",
    ]
    if p.customInstructions:
        parts.append(f"Extra instructions from the user: {p.customInstructions}")
    if memory_block:
        parts.append(memory_block)
    parts.append(TOOL_POLICY)
    return "\n".join(parts)


def _get_or_create_conversation(db: Session, user_id: str, conversation_id: int | None) -> Conversation:
    if conversation_id is not None:
        conv = db.get(Conversation, conversation_id)
        if conv is not None and conv.user_id == user_id:
            return conv
    conv = Conversation(user_id=user_id, title="New Chat")
    db.add(conv)
    db.commit()
    db.refresh(conv)
    return conv


def _persist_turn(db: Session, conv, user_id: str, user_text: str, reply: str) -> None:
    if user_text:
        db.add(Message(conversation_id=conv.id, user_id=user_id, role="user", content=user_text))
    if reply.strip():
        db.add(Message(conversation_id=conv.id, user_id=user_id, role="assistant", content=reply))
    db.commit()


def handle_chat(db: Session, user_id: str, req: ChatRequest):
    conv = _get_or_create_conversation(db, user_id, req.conversation_id)

    # Cloud-first: load the user's personality from Postgres (fall back to what the
    # request carried, then the default).
    personality = req.personality or Personality()
    row = db.get(PersonalityRow, user_id)
    if row is not None:
        try:
            personality = Personality(**json.loads(row.data))
        except Exception:
            pass
    now = req.clientNow or datetime.now(timezone.utc).isoformat()
    if req.timezone:
        now = f"{now} ({req.timezone})"

    last_user = next((m.content for m in reversed(req.messages) if m.role == "user"), "")

    # Auto-title conversation if it's new
    if conv.title in (None, "Chat", "New Chat", "") and last_user:
        clean_title = last_user.strip().replace("\n", " ")[:36]
        if clean_title:
            conv.title = clean_title
            db.commit()

    # Auto-detect explicit name statements (e.g. "my name is Komal")
    import re
    m_name = re.search(r"\b(?:my name is|call me|i am)\s+([a-z0-9_-]+)", last_user, re.IGNORECASE)
    if m_name and len(m_name.group(1)) > 1 and m_name.group(1).lower() not in ("a", "the", "here", "ready", "going"):
        val = f"User's name is {m_name.group(1).capitalize()}"
        from ..memory.engine import save_memory
        save_memory(db, user_id, "fact", "identity", val)

    memories = retrieve(db, user_id, last_user) if last_user else []
    system = _build_system_prompt(personality, now, build_context_block(memories))

    convo: list[dict] = [{"role": m.role, "content": m.content} for m in req.messages]
    ctx = ToolContext(
        db=db, user_id=user_id, google_access_token=req.googleAccessToken, timezone=req.timezone
    )

    # ChatGPT-style attachment on this message: an IMAGE goes to the vision model
    # and returns directly; a FILE has its text extracted and prepended as context.
    if req.attachment is not None:
        att = req.attachment
        if att.mimeType.startswith("image/"):
            data_uri = f"data:{att.mimeType};base64,{att.dataBase64}"
            try:
                reply = ai_service.generate_vision(
                    system, last_user or "Describe this image.", data_uri
                )
            except Exception as e:  # noqa: BLE001
                if "429" in str(e) or "rate limit" in str(e).lower():
                    raise
                reply = "I couldn't read that image right now. Please try again shortly."
            _persist_turn(db, conv, user_id, last_user or f"📎 {att.filename}", reply)
            audit.record(db, user_id, "chat_image", f"conv={conv.id} file={att.filename}")
            return reply, ai_service.provider, conv.id, [], []
        else:
            from ..services.documents import extract_text

            try:
                raw = base64.b64decode(att.dataBase64)
            except Exception:
                raw = b""
            text = extract_text(att.filename, att.mimeType, raw)
            if text and convo:
                convo[-1]["content"] = (
                    f"[Attached file '{att.filename}']:\n{text[:8000]}\n\n{convo[-1]['content']}"
                )

    device_calls: list[ToolCallOut] = []
    pending: list[ToolCallOut] = []
    reply, provider = "", ai_service.provider

    # Tool loop with proper OpenAI tool-message threading: we append the model's
    # tool-call turn, then a `tool` result message per call. This is what tells the
    # model a tool already ran, so it stops re-issuing the SAME call every pass
    # (the old code fed results back as plain text, so identical actions like
    # save_memory / create_task fired once per loop — up to MAX_TOOL_LOOPS times).
    for _ in range(MAX_TOOL_LOOPS):
        reply, calls, assistant_message = ai_service.generate_with_tools(
            system, convo, tool_specs()
        )
        if not calls:
            break  # the model answered with plain text — done.
        # Record the assistant's tool-call turn before any tool results (required
        # by the API: every tool_call_id must be answered by a tool message).
        convo.append(assistant_message)
        for c in calls:
            valid = validate_call(c["name"], c["args"])
            if valid is None:
                convo.append(
                    {"role": "tool", "tool_call_id": c["id"], "content": "Invalid call; skipped."}
                )
                continue
            summary = _summarize(valid.name, valid.args)
            if valid.confirmation == "always":
                # Approval Engine: do NOT execute — return for the user to confirm.
                pending.append(ToolCallOut(**valid.__dict__, summary=summary))
                convo.append(
                    {
                        "role": "tool",
                        "tool_call_id": c["id"],
                        "content": f"Held for the user to confirm: {summary}. Do not call again.",
                    }
                )
            elif valid.runs_on == "device":
                device_calls.append(ToolCallOut(**valid.__dict__, summary=summary))
                convo.append(
                    {
                        "role": "tool",
                        "tool_call_id": c["id"],
                        "content": "Scheduled on the user's device. Done — do not call again.",
                    }
                )
            else:
                result = execute_backend(valid, ctx)
                audit.record(db, user_id, "tool_call", f"{valid.name}: {result[:120]}")
                convo.append({"role": "tool", "tool_call_id": c["id"], "content": result})

    # If the model ended on tool calls with no text (and it wasn't a device/approval
    # turn), force a final plain-text reply.
    if not reply.strip() and not device_calls and not pending:
        reply = ai_service.generate(system, convo)

    if last_user:
        db.add(Message(conversation_id=conv.id, user_id=user_id, role="user", content=last_user))
    if reply.strip():
        db.add(Message(conversation_id=conv.id, user_id=user_id, role="assistant", content=reply))
    db.commit()
    audit.record(db, user_id, "chat", f"conv={conv.id} tools={[c.name for c in device_calls]}")

    return reply, provider, conv.id, device_calls, pending
