"""Intent Detection (blueprint §6): decide whether a request is a simple one-shot
message (→ normal chat) or a multi-step goal (→ agent run). Heuristic-first to
save tokens; the planner does the real decomposition."""
import re

# Cues that a request is likely multi-step / agentic.
_MULTI = re.compile(
    r"\b(and then|then |after that|also |, and |schedule|book|organi[sz]e|plan |summar|"
    r"follow up|find .* and|research)\b",
    re.IGNORECASE,
)


def is_agentic(goal: str) -> bool:
    """True when the request looks like it needs planning + multiple steps."""
    if len(goal) > 140:
        return True
    return bool(_MULTI.search(goal))
