"""Agent Run Manager (blueprint §6): executes a plan step-by-step, evaluating each
result and retrying once on failure, tracking everything in agent_runs/agent_steps.
Sensitive steps (send_email, cancel_event) pause for approval via the Approval
Engine rather than running. Reuses the Tool Engine."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from .. import audit
from ..ai.service import ai_service
from ..models import AgentRun, AgentStep
from ..tools.base import ToolContext
from ..tools.registry import execute_backend, tool_specs, validate_call
from .planner import make_plan

MAX_ATTEMPTS = 2
_FAIL_MARKERS = ("not connected", "failed", "error:", "cannot run")


def _summarize(name: str, args: dict) -> str:
    if name == "send_email":
        return f'Send email to {args.get("to", "?")} — "{args.get("subject") or "(no subject)"}"'
    if name == "cancel_calendar_event":
        return "Cancel a calendar event"
    if name == "update_calendar_event":
        return "Update a calendar event"
    return name


def _execute_step(desc: str, ctx: ToolContext, now: str, done_so_far: list[str]):
    """Run one step. Returns (result_text, tool_name, pending, device, ok)."""
    context = "\n".join(done_so_far) if done_so_far else "(nothing yet)"
    system = (
        "You are executing ONE step of a plan. You MUST carry out the step by CALLING the correct "
        "tool with the right arguments — do not describe it or claim it is done without calling a "
        "tool. Only answer in plain text if the step genuinely needs no tool (e.g. summarising). "
        f"Current time: {now}.\nResults so far:\n{context}"
    )
    try:
        reply, raw_calls = ai_service.generate_with_tools(
            system, [{"role": "user", "content": desc}], tool_specs()
        )
    except Exception as e:  # noqa: BLE001
        return f"error: {e}", None, [], [], False

    results: list[str] = []
    pending: list[dict] = []
    device: list[dict] = []
    tool_name: str | None = None
    for raw in raw_calls:
        valid = validate_call(raw["name"], raw["args"])
        if valid is None:
            continue
        tool_name = valid.name
        if valid.confirmation == "always":
            pending.append({"name": valid.name, "args": valid.args, "summary": _summarize(valid.name, valid.args)})
        elif valid.runs_on == "backend":
            results.append(execute_backend(valid, ctx))
        else:
            device.append({"name": valid.name, "args": valid.args})

    result_text = reply or "; ".join(results) or "(no action taken)"
    ok = not any(m in result_text.lower() for m in _FAIL_MARKERS)
    return result_text, tool_name, pending, device, ok


def run_agent(db: Session, user_id: str, goal: str, ctx: ToolContext, now: str) -> dict:
    run = AgentRun(user_id=user_id, goal=goal, status="running")
    db.add(run)
    db.commit()
    db.refresh(run)

    plan = make_plan(goal, now)
    done_so_far: list[str] = []
    pending_all: list[dict] = []
    device_all: list[dict] = []
    overall = "done"

    for i, desc in enumerate(plan):
        step = AgentStep(run_id=run.id, idx=i, description=desc, status="running", attempts=0)
        db.add(step)
        db.commit()

        result, tool_name, pending, device, ok = _execute_step(desc, ctx, now, done_so_far)
        step.attempts = 1
        if not ok and not pending and step.attempts < MAX_ATTEMPTS:
            result, tool_name, pending, device, ok = _execute_step(desc, ctx, now, done_so_far)
            step.attempts = 2

        step.tool_name = tool_name
        step.result = result
        if pending:
            step.status = "awaiting_approval"
            pending_all.extend(pending)
            overall = "awaiting_approval"
        elif ok:
            step.status = "done"
        else:
            step.status = "failed"
            if overall != "awaiting_approval":
                overall = "failed"
        device_all.extend(device)
        done_so_far.append(f"Step {i + 1} ({desc}): {result}")
        db.commit()

    run.status = overall
    run.summary = " ".join(done_so_far)[:2000]
    run.finished_at = datetime.now(timezone.utc)
    db.commit()
    audit.record(db, user_id, "agent_run", f"run={run.id} status={overall} steps={len(plan)}")

    return {
        "run_id": run.id,
        "status": overall,
        "goal": goal,
        "steps": [
            {"idx": s.idx, "description": s.description, "status": s.status, "result": s.result}
            for s in run.steps
        ],
        "pendingConfirmations": pending_all,
        "toolCalls": device_all,
    }
