"""Location tools: save named places + list them (backend), and create a
geofence reminder (device — the phone registers the actual geofence)."""
from pydantic import BaseModel, Field
from sqlalchemy import select

from ..models import SavedLocation
from .base import Tool, ToolContext


# --- save_location (backend) ---
class SaveLocationArgs(BaseModel):
    label: str = Field(min_length=1, max_length=120)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    radius_m: int = Field(default=150, ge=50, le=5000)


def _save_location(args: SaveLocationArgs, ctx: ToolContext) -> str:
    row = SavedLocation(
        user_id=ctx.user_id, label=args.label, latitude=args.latitude,
        longitude=args.longitude, radius_m=args.radius_m,
    )
    ctx.db.add(row)
    ctx.db.commit()
    return f'Saved location "{args.label}".'


save_location_tool = Tool(
    name="save_location",
    description=(
        "Save a named place (Home, Office, Gym) with coordinates so it can be used "
        "for location reminders later. The phone provides latitude/longitude (from "
        "the current position or a picked point)."
    ),
    parameters={
        "type": "object",
        "properties": {
            "label": {"type": "string"},
            "latitude": {"type": "number"},
            "longitude": {"type": "number"},
            "radius_m": {"type": "integer", "description": "Trigger radius in metres (default 150)."},
        },
        "required": ["label", "latitude", "longitude"],
        "additionalProperties": False,
    },
    args_model=SaveLocationArgs,
    confirmation="never",
    runs_on="backend",
    execute=_save_location,
)


# --- list_locations (backend) ---
class ListLocationsArgs(BaseModel):
    pass


def _list_locations(args: ListLocationsArgs, ctx: ToolContext) -> str:
    rows = ctx.db.execute(
        select(SavedLocation).where(SavedLocation.user_id == ctx.user_id)
    ).scalars().all()
    if not rows:
        return "No saved locations yet."
    return "\n".join(
        f'{r.label}: {r.latitude:.5f},{r.longitude:.5f} (r={r.radius_m}m)' for r in rows
    )


list_locations_tool = Tool(
    name="list_locations",
    description="List the user's saved places with their coordinates, so you can "
    "reference one (e.g. to create a location reminder near it).",
    parameters={"type": "object", "properties": {}, "additionalProperties": False},
    args_model=ListLocationsArgs,
    confirmation="never",
    runs_on="backend",
    execute=_list_locations,
)


# --- create_location_reminder (device — phone registers the geofence) ---
class LocationReminderArgs(BaseModel):
    text: str = Field(min_length=1, max_length=500)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    radius_m: int = Field(default=150, ge=50, le=5000)
    label: str | None = Field(default=None, max_length=120)


create_location_reminder_tool = Tool(
    name="create_location_reminder",
    description=(
        "Remind the user of something when they are near a place — a GEOFENCE "
        "reminder. Provide the text and the target latitude/longitude (look them up "
        "with list_locations if the user names a saved place). The phone registers "
        "the geofence and fires a local notification on arrival."
    ),
    parameters={
        "type": "object",
        "properties": {
            "text": {"type": "string"},
            "latitude": {"type": "number"},
            "longitude": {"type": "number"},
            "radius_m": {"type": "integer", "description": "Trigger radius in metres (default 150)."},
            "label": {"type": "string", "description": "Optional place name for the message."},
        },
        "required": ["text", "latitude", "longitude"],
        "additionalProperties": False,
    },
    args_model=LocationReminderArgs,
    confirmation="never",
    runs_on="device",
)
