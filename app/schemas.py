"""Pydantic request/response models (structured validation per the blueprint)."""
from typing import Literal
from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str = Field(min_length=1, max_length=8000)


class Personality(BaseModel):
    name: str = "Wiora"
    tone: str = "Friendly"
    formality: str = "Casual-professional"
    responseLength: str = "Concise"
    humor: str = "Light"
    warmth: str = "Warm"
    confidence: str = "Confident"
    proactivity: str = "Balanced"
    confirmationLevel: str = "Balanced"
    customInstructions: str = ""


class Attachment(BaseModel):
    filename: str = Field(max_length=300)
    mimeType: str = Field(max_length=128)
    dataBase64: str = Field(min_length=1)


class Coordinates(BaseModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)


class ChatRequest(BaseModel):
    messages: list[ChatMessage] = Field(min_length=1, max_length=50)
    conversation_id: int | None = None
    personality: Personality | None = None
    clientNow: str | None = None
    timezone: str | None = None
    googleAccessToken: str | None = None  # phone-owned, used transiently for Gmail/Calendar
    attachment: Attachment | None = None  # a file/image attached to this message
    location: Coordinates | None = None  # phone's current position (for "save here" etc.)


class ToolCallOut(BaseModel):
    name: str
    args: dict
    confirmation: str
    runs_on: str
    summary: str = ""  # human-readable, for the approval prompt


class ChatResponse(BaseModel):
    reply: str
    provider: str
    conversation_id: int
    toolCalls: list[ToolCallOut] = []  # device tools the phone runs (e.g. reminders)
    pendingConfirmations: list[ToolCallOut] = []  # need the user's approval first


class ConfirmToolRequest(BaseModel):
    name: str
    args: dict
    timezone: str | None = None
    googleAccessToken: str | None = None


class AgentRunRequest(BaseModel):
    goal: str = Field(min_length=1, max_length=2000)
    clientNow: str | None = None
    timezone: str | None = None
    googleAccessToken: str | None = None


# --- Cloud-first data (were local SQLite; now Postgres) ---
class ReminderIn(BaseModel):
    text: str = Field(min_length=1, max_length=500)
    dueAt: str | None = None  # ISO 8601


class ReminderOut(BaseModel):
    id: int
    text: str
    dueAt: str | None
    done: bool
    createdAt: str


class MeetingIn(BaseModel):
    title: str = Field(max_length=200)
    transcript: str = ""
    insights: dict | None = None


class MeetingOut(BaseModel):
    id: int
    title: str
    transcript: str
    insights: dict | None
    createdAt: str


class ConversationOut(BaseModel):
    id: int
    title: str
    createdAt: str
    preview: str
    messageCount: int


class MessageOut(BaseModel):
    id: int
    role: str
    content: str


class PreferenceIn(BaseModel):
    key: str = Field(max_length=64)
    value: str = Field(max_length=2000)


class TaskIn(BaseModel):
    text: str = Field(min_length=1, max_length=500)
    dueAt: str | None = None


class TaskOut(BaseModel):
    id: int
    text: str
    done: bool
    dueAt: str | None
    createdAt: str


class LocationIn(BaseModel):
    label: str = Field(min_length=1, max_length=120)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    radiusM: int = Field(default=150, ge=50, le=5000)


class LocationOut(BaseModel):
    id: int
    label: str
    latitude: float
    longitude: float
    radiusM: int
    createdAt: str


class DocumentIn(BaseModel):
    filename: str = Field(min_length=1, max_length=300)
    mimeType: str = Field(max_length=128)
    dataBase64: str = Field(min_length=1)


class DocumentOut(BaseModel):
    id: int
    filename: str
    mimetype: str
    textPreview: str
    createdAt: str


# --- Memory management (blueprint V1 §3.4: view / edit / delete memory) ---
class MemoryOut(BaseModel):
    id: int
    type: str
    category: str | None
    value: str
    createdAt: str


class MemoryUpdate(BaseModel):
    value: str | None = Field(default=None, max_length=2000)
    category: str | None = Field(default=None, max_length=64)


# --- Daily Briefing (blueprint V2 §9) ---
class BriefingRequest(BaseModel):
    clientNow: str | None = None  # phone's local ISO datetime (with offset)
    timezone: str | None = None
    googleAccessToken: str | None = None  # phone-owned, transient — for the calendar


class BriefingEvent(BaseModel):
    summary: str
    start: str
    location: str = ""


class BriefingItem(BaseModel):
    id: int
    text: str
    dueAt: str | None = None


class BriefingOut(BaseModel):
    greeting: str
    dateLabel: str
    summary: str  # short natural-language briefing from the assistant
    events: list[BriefingEvent] = []
    tasks: list[BriefingItem] = []
    reminders: list[BriefingItem] = []


class HealthResponse(BaseModel):
    ok: bool
    provider: str
    database: bool
    auth: bool
    embeddings: str
    redis: str
