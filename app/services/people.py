"""Google People API (blueprint §11 Contacts). Uses the phone-sent token; lists
the user's connections and filters by query. Needs the contacts.readonly scope."""
from __future__ import annotations

import httpx

PEOPLE = "https://people.googleapis.com/v1"


def search_contacts(token: str, query: str, max_results: int = 10) -> list[dict]:
    r = httpx.get(
        f"{PEOPLE}/people/me/connections",
        params={"personFields": "names,emailAddresses,phoneNumbers", "pageSize": 500},
        headers={"Authorization": f"Bearer {token}"},
        timeout=20,
    )
    r.raise_for_status()
    q = query.lower().strip()
    out: list[dict] = []
    for c in r.json().get("connections", []):
        name = (c.get("names") or [{}])[0].get("displayName", "")
        emails = [e.get("value", "") for e in c.get("emailAddresses", [])]
        phones = [p.get("value", "") for p in c.get("phoneNumbers", [])]
        hay = f"{name} {' '.join(emails)}".lower()
        if not q or q in hay:
            out.append({"name": name, "emails": emails, "phones": phones})
        if len(out) >= max_results:
            break
    return out
