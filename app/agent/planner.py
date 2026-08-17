"""Planner (blueprint §6): break a complex goal into an ordered list of concrete
steps. Also does lightweight Intent Detection — a trivial goal yields one step."""
from __future__ import annotations

import json
import re

from ..ai.service import ai_service
from ..tools.registry import REGISTRY

_SYSTEM = "\n".join(
    [
        "You are a task planner for a personal assistant.",
        "Break the user's goal into a SHORT ordered list of concrete steps (1-6).",
        "Each step MUST be a complete, self-contained instruction written as an imperative "
        "sentence, INCLUDING every detail from the goal it needs (names, dates/times, email "
        "addresses, message content). Example: 'Create a reminder to call Rahul tomorrow at 5 PM'.",
        "Do NOT output bare tool names as steps. Keep each step to a single action.",
        "If the goal is one simple request, return exactly one step.",
        '(The assistant can: ' + ", ".join(REGISTRY.keys()) + ".)",
        'Respond with ONLY JSON: {"steps": ["step 1", "step 2", ...]}. No prose.',
    ]
)


def make_plan(goal: str, now: str) -> list[str]:
    reply = ai_service.generate(
        _SYSTEM, [{"role": "user", "content": f"Current time: {now}\nGoal: {goal}"}]
    )
    cleaned = re.sub(r"```json|```", "", reply)
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start != -1 and end > start:
        try:
            data = json.loads(cleaned[start : end + 1])
            steps = [str(s) for s in data.get("steps", []) if str(s).strip()]
            if steps:
                return steps[:6]
        except json.JSONDecodeError:
            pass
    # Fallback: treat the whole goal as one step.
    return [goal]
