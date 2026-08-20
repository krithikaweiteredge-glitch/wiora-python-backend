"""Tool Engine base (blueprint §7): every external capability is an independent,
validated Tool. The AI can only REQUEST a tool; the backend validates args and
executes. Device-side tools (e.g. reminders) are forwarded to the phone."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Literal

from pydantic import BaseModel
from sqlalchemy.orm import Session


@dataclass
class ToolContext:
    db: Session
    user_id: str
    google_access_token: str | None = None
    timezone: str | None = None
    # The phone's current position (sent per request), for "save this location" and
    # resolving "near here". None when location permission isn't granted.
    user_lat: float | None = None
    user_lng: float | None = None


@dataclass
class Tool:
    name: str
    description: str
    parameters: dict  # JSON Schema shown to the model
    args_model: type[BaseModel]  # Pydantic validation of the model's args
    confirmation: Literal["always", "sensitive", "never"]
    runs_on: Literal["device", "backend"]
    # Present only for runs_on="backend": returns a short result string.
    execute: Callable[[BaseModel, ToolContext], str] | None = None

    def spec(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }

    def validate(self, args: dict) -> BaseModel | None:
        try:
            return self.args_model(**args)
        except Exception:
            return None
