"""On-device action tools — the backend validates the request and forwards it to
the phone, which performs the OS action (alarm, timer, dialer, WhatsApp).

None of these touch the network or the user's data on the server; they only
translate a natural-language request into a validated, structured device call.
The phone still shows the dialer / WhatsApp send button, so the user stays in
control of the final send/call."""
from pydantic import BaseModel, Field

from .base import Tool


# --- set_alarm --------------------------------------------------------------
class SetAlarmArgs(BaseModel):
    hour: int = Field(ge=0, le=23)
    minute: int = Field(default=0, ge=0, le=59)
    label: str | None = Field(default=None, max_length=120)


set_alarm_tool = Tool(
    name="set_alarm",
    description=(
        "Set an alarm on the user's phone at a specific clock time. Convert spoken "
        "times into 24-hour numbers: '7am' -> hour 7, minute 0; '6:30 PM' -> hour 18, "
        "minute 30; 'quarter to nine in the morning' -> hour 8, minute 45. Use the "
        "user's local time. Add a short label when they name one ('wake up', 'gym')."
    ),
    parameters={
        "type": "object",
        "properties": {
            "hour": {"type": "integer", "description": "Hour in 24-hour format (0-23)."},
            "minute": {"type": "integer", "description": "Minute (0-59). Default 0."},
            "label": {"type": "string", "description": "Optional short label for the alarm."},
        },
        "required": ["hour"],
        "additionalProperties": False,
    },
    args_model=SetAlarmArgs,
    confirmation="never",
    runs_on="device",
)


# --- set_timer --------------------------------------------------------------
class SetTimerArgs(BaseModel):
    duration_seconds: int = Field(ge=1, le=86400)
    label: str | None = Field(default=None, max_length=120)


set_timer_tool = Tool(
    name="set_timer",
    description=(
        "Start a countdown timer on the user's phone. Convert the spoken duration into "
        "TOTAL seconds: '10 minutes' -> 600; '90 seconds' -> 90; '1 hour 30 minutes' -> "
        "5400; 'half an hour' -> 1800. Add a short label when they name one "
        "('pasta', 'tea')."
    ),
    parameters={
        "type": "object",
        "properties": {
            "duration_seconds": {
                "type": "integer",
                "description": "Total timer length in seconds.",
            },
            "label": {"type": "string", "description": "Optional short label for the timer."},
        },
        "required": ["duration_seconds"],
        "additionalProperties": False,
    },
    args_model=SetTimerArgs,
    confirmation="never",
    runs_on="device",
)


# --- call_contact -----------------------------------------------------------
class CallContactArgs(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    # Optional: if the user gives an explicit number, pass it through directly.
    number: str | None = Field(default=None, max_length=40)


call_contact_tool = Tool(
    name="call_contact",
    description=(
        "Call a person by name. The phone looks the name up in the user's contacts and "
        "opens the dialer with the number ready — the user taps the call button. Pass "
        "'name' as the person said it ('Rahul', 'Mom'). Only pass 'number' if the user "
        "spoke an explicit phone number to dial instead of a saved contact."
    ),
    parameters={
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "The contact's name to call."},
            "number": {
                "type": "string",
                "description": "An explicit phone number, only if the user dictated one.",
            },
        },
        "required": ["name"],
        "additionalProperties": False,
    },
    args_model=CallContactArgs,
    confirmation="never",
    runs_on="device",
)


# --- send_whatsapp ----------------------------------------------------------
class SendWhatsappArgs(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    message: str = Field(min_length=1, max_length=2000)
    number: str | None = Field(default=None, max_length=40)


send_whatsapp_tool = Tool(
    name="send_whatsapp",
    description=(
        "Send a WhatsApp message to a contact. The phone looks the name up in contacts "
        "and opens the WhatsApp chat with the message pre-filled — the user taps send. "
        "Pass 'name' as spoken and 'message' as the exact text to send. Only pass "
        "'number' if the user dictated an explicit phone number instead of a contact."
    ),
    parameters={
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "The contact's name to message."},
            "message": {"type": "string", "description": "The message text to pre-fill."},
            "number": {
                "type": "string",
                "description": "An explicit phone number, only if the user dictated one.",
            },
        },
        "required": ["name", "message"],
        "additionalProperties": False,
    },
    args_model=SendWhatsappArgs,
    confirmation="never",
    runs_on="device",
)


# --- read_whatsapp ----------------------------------------------------------
class ReadWhatsappArgs(BaseModel):
    limit: int = Field(default=10, ge=1, le=50)
    # Optional: only messages from a sender whose name contains this text.
    contact: str | None = Field(default=None, max_length=120)


read_whatsapp_tool = Tool(
    name="read_whatsapp",
    description=(
        "Read the user's RECENT incoming WhatsApp messages that Wiora captured from "
        "notifications. IMPORTANT: this only covers NEW messages that arrived while "
        "Wiora's notification access was enabled — there is NO access to full chat "
        "history. Use when the user asks to read/check/see their WhatsApp messages. "
        "Optionally set 'contact' to filter to one sender. If the user hasn't enabled "
        "access yet, the phone will prompt them to turn it on."
    ),
    parameters={
        "type": "object",
        "properties": {
            "limit": {
                "type": "integer",
                "description": "How many recent messages to show (1-50, default 10).",
            },
            "contact": {
                "type": "string",
                "description": "Optional sender name to filter the messages by.",
            },
        },
        "required": [],
        "additionalProperties": False,
    },
    args_model=ReadWhatsappArgs,
    confirmation="never",
    runs_on="device",
)
