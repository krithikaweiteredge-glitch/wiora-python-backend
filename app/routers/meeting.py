"""Meeting insight extraction (Phase 9 / blueprint knowledge features). Transcript
→ structured insights via the AIService. Nothing stored server-side here."""
import json
import re

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..ai.service import ai_service

router = APIRouter()


class ExtractBody(BaseModel):
    transcript: str = Field(min_length=1, max_length=60000)
    projectName: str | None = None


_SYSTEM = "\n".join(
    [
        "You extract structured notes from a meeting transcript.",
        "Respond with ONLY a JSON object (no prose, no code fences) with exactly these keys:",
        '{"summary": string, "decisions": string[], "actionItems": [{"text": string, '
        '"owner": string, "due": string}], "openQuestions": string[], "people": string[], '
        '"requirements": string[]}',
        "Use empty strings for unknown owner/due. Keep the summary to 3-5 sentences.",
    ]
)


def _parse_json_object(text: str) -> dict | None:
    cleaned = re.sub(r"```json|```", "", text)
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start == -1 or end <= start:
        return None
    try:
        return json.loads(cleaned[start : end + 1])
    except json.JSONDecodeError:
        return None


def _as_list(v) -> list[str]:
    return [str(x) for x in v] if isinstance(v, list) else []


@router.post("/api/meeting/extract")
def extract(body: ExtractBody) -> dict:
    header = f"Project: {body.projectName}\n\nTranscript:\n" if body.projectName else "Transcript:\n"
    try:
        reply = ai_service.generate(_SYSTEM, [{"role": "user", "content": header + body.transcript}])
    except Exception as e:  # noqa: BLE001
        if "429" in str(e) or "rate limit" in str(e).lower():
            raise HTTPException(status_code=429, detail="Daily AI limit reached — try again later.")
        raise HTTPException(status_code=500, detail="Failed to process the meeting.")

    data = _parse_json_object(reply)
    if data is None:
        raise HTTPException(status_code=502, detail="Could not structure the meeting notes.")

    action_items = []
    if isinstance(data.get("actionItems"), list):
        for a in data["actionItems"]:
            if isinstance(a, dict):
                action_items.append(
                    {
                        "text": str(a.get("text", "")),
                        "owner": str(a.get("owner", "")),
                        "due": str(a.get("due", "")),
                    }
                )

    return {
        "provider": ai_service.provider,
        "insights": {
            "summary": str(data.get("summary", "")),
            "decisions": _as_list(data.get("decisions")),
            "actionItems": action_items,
            "openQuestions": _as_list(data.get("openQuestions")),
            "people": _as_list(data.get("people")),
            "requirements": _as_list(data.get("requirements")),
        },
    }
