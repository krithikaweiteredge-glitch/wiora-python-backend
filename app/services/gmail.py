"""Gmail REST client (httpx). The phone sends the Google access token per request;
we use it transiently. Nothing stored server-side beyond what the app persists."""
from __future__ import annotations

import base64
from urllib.parse import quote

import httpx

GMAIL = "https://gmail.googleapis.com/gmail/v1/users/me"


def _get(token: str, path: str) -> dict:
    r = httpx.get(f"{GMAIL}{path}", headers={"Authorization": f"Bearer {token}"}, timeout=20)
    r.raise_for_status()
    return r.json()


def _headers(msg: dict) -> dict:
    hs = msg.get("payload", {}).get("headers", [])

    def g(name: str) -> str:
        return next((h["value"] for h in hs if h["name"].lower() == name.lower()), "")

    return {"from": g("From"), "subject": g("Subject"), "date": g("Date")}


def _b64url_decode(data: str) -> str:
    return base64.urlsafe_b64decode(data + "===").decode("utf-8", "ignore")


def _plain_text(payload: dict) -> str:
    if not payload:
        return ""
    if payload.get("mimeType") == "text/plain" and payload.get("body", {}).get("data"):
        return _b64url_decode(payload["body"]["data"])
    for part in payload.get("parts", []) or []:
        found = _plain_text(part)
        if found:
            return found
    if payload.get("mimeType") == "text/html" and payload.get("body", {}).get("data"):
        import re
        return re.sub(r"<[^>]+>", " ", _b64url_decode(payload["body"]["data"]))
    return ""


def search_messages(token: str, query: str, max_results: int = 10) -> list[dict]:
    listing = _get(token, f"/messages?q={quote(query)}&maxResults={max_results}")
    rows = []
    for m in listing.get("messages", [])[:max_results]:
        msg = _get(
            token,
            f"/messages/{m['id']}?format=metadata&metadataHeaders=From&metadataHeaders=Subject&metadataHeaders=Date",
        )
        rows.append({"id": m["id"], "snippet": msg.get("snippet", ""), **_headers(msg)})
    return rows


def read_message(token: str, msg_id: str) -> dict:
    msg = _get(token, f"/messages/{msg_id}?format=full")
    return {**_headers(msg), "body": _plain_text(msg.get("payload", {}))[:6000]}


def _raw_message(to: str, subject: str, body: str) -> str:
    raw_bytes = "\r\n".join(
        [f"To: {to}", f"Subject: {subject}", "Content-Type: text/plain; charset=UTF-8", "", body]
    ).encode("utf-8")
    return base64.urlsafe_b64encode(raw_bytes).decode("ascii")


def create_draft(token: str, to: str, subject: str, body: str) -> str:
    r = httpx.post(
        f"{GMAIL}/drafts",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={"message": {"raw": _raw_message(to, subject, body)}},
        timeout=20,
    )
    r.raise_for_status()
    return r.json().get("id", "")


def send_message(token: str, to: str, subject: str, body: str) -> str:
    r = httpx.post(
        f"{GMAIL}/messages/send",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={"raw": _raw_message(to, subject, body)},
        timeout=20,
    )
    r.raise_for_status()
    return r.json().get("id", "")
