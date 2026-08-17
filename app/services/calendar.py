"""Google Calendar REST client (httpx). Phone-owned token used transiently."""
from __future__ import annotations

from datetime import datetime
from urllib.parse import quote

import httpx

CAL = "https://www.googleapis.com/calendar/v3"


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def list_events(token: str, time_min: str, time_max: str, max_results: int = 10) -> list[dict]:
    q = (
        f"?timeMin={quote(time_min)}&timeMax={quote(time_max)}"
        f"&singleEvents=true&orderBy=startTime&maxResults={max_results}"
    )
    r = httpx.get(f"{CAL}/calendars/primary/events{q}", headers=_headers(token), timeout=20)
    r.raise_for_status()
    out = []
    for e in r.json().get("items", []):
        out.append(
            {
                "id": e.get("id", ""),
                "summary": e.get("summary", "(no title)"),
                "start": e.get("start", {}).get("dateTime") or e.get("start", {}).get("date", ""),
                "end": e.get("end", {}).get("dateTime") or e.get("end", {}).get("date", ""),
                "location": e.get("location", ""),
            }
        )
    return out


def update_event(
    token: str,
    event_id: str,
    tz: str,
    summary: str | None = None,
    start_iso: str | None = None,
    end_iso: str | None = None,
    location: str | None = None,
) -> str:
    patch: dict = {}
    if summary:
        patch["summary"] = summary
    if location:
        patch["location"] = location
    if start_iso:
        patch["start"] = {"dateTime": start_iso, "timeZone": tz}
    if end_iso:
        patch["end"] = {"dateTime": end_iso, "timeZone": tz}
    r = httpx.patch(
        f"{CAL}/calendars/primary/events/{event_id}",
        headers=_headers(token),
        json=patch,
        timeout=20,
    )
    r.raise_for_status()
    return r.json().get("htmlLink", "")


def delete_event(token: str, event_id: str) -> None:
    r = httpx.delete(f"{CAL}/calendars/primary/events/{event_id}", headers=_headers(token), timeout=20)
    if r.status_code not in (200, 204):
        r.raise_for_status()


def create_event(
    token: str, summary: str, start_iso: str, end_iso: str, tz: str, location: str | None = None
) -> str:
    body = {
        "summary": summary,
        "start": {"dateTime": start_iso, "timeZone": tz},
        "end": {"dateTime": end_iso, "timeZone": tz},
    }
    if location:
        body["location"] = location
    r = httpx.post(f"{CAL}/calendars/primary/events", headers=_headers(token), json=body, timeout=20)
    r.raise_for_status()
    return r.json().get("htmlLink", "")


def find_free_slots(token: str, time_min: str, time_max: str, min_minutes: int = 30) -> list[dict]:
    r = httpx.post(
        f"{CAL}/freeBusy",
        headers=_headers(token),
        json={"timeMin": time_min, "timeMax": time_max, "items": [{"id": "primary"}]},
        timeout=20,
    )
    r.raise_for_status()
    busy = r.json().get("calendars", {}).get("primary", {}).get("busy", [])

    def ts(s: str) -> float:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()

    window_start, window_end = ts(time_min), ts(time_max)
    blocks = sorted(({"s": ts(b["start"]), "e": ts(b["end"])} for b in busy), key=lambda b: b["s"])
    min_s = min_minutes * 60
    free, cursor = [], window_start
    for b in blocks:
        if b["s"] - cursor >= min_s:
            free.append(
                {
                    "start": datetime.fromtimestamp(cursor).isoformat(),
                    "end": datetime.fromtimestamp(b["s"]).isoformat(),
                }
            )
        cursor = max(cursor, b["e"])
    if window_end - cursor >= min_s:
        free.append(
            {
                "start": datetime.fromtimestamp(cursor).isoformat(),
                "end": datetime.fromtimestamp(window_end).isoformat(),
            }
        )
    return free
