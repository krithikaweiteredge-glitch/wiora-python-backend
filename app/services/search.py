"""Web search provider (blueprint: agent tools). Tavily by default; Brave/Serper
supported. Returns a short text digest of the top results, or a clear
"not configured" message when no API key is set — never raises to the caller."""
from __future__ import annotations

import httpx

from ..config import get_settings

settings = get_settings()


def is_configured() -> bool:
    return bool(settings.search_api_key)


def search(query: str, max_results: int = 5) -> str:
    if not is_configured():
        return (
            "Web search is not configured. Ask the user to set SEARCH_API_KEY "
            "(a free Tavily key from tavily.com) to enable it."
        )
    # Cache identical queries for 10 min (Redis) so repeat lookups are free/fast.
    from .. import cache

    ckey = f"search:{settings.search_provider}:{query.lower().strip()}"
    hit = cache.cache_get(ckey)
    if hit is not None:
        return hit

    provider = settings.search_provider.lower()
    try:
        if provider == "brave":
            result = _brave(query, max_results)
        elif provider == "serper":
            result = _serper(query, max_results)
        else:
            result = _tavily(query, max_results)
    except Exception as e:  # noqa: BLE001
        return f"Web search failed: {e}"

    cache.cache_set(ckey, result, ttl_seconds=600)
    return result


def _digest(items: list[tuple[str, str, str]]) -> str:
    """items: (title, url, snippet) -> compact text block for the model."""
    if not items:
        return "No results found."
    return "\n\n".join(f"{t}\n{u}\n{s}".strip() for t, u, s in items)


def _tavily(query: str, n: int) -> str:
    r = httpx.post(
        "https://api.tavily.com/search",
        json={
            "api_key": settings.search_api_key,
            "query": query,
            "max_results": n,
            "include_answer": True,
        },
        timeout=30,
    )
    r.raise_for_status()
    data = r.json()
    items = [(x.get("title", ""), x.get("url", ""), x.get("content", "")) for x in data.get("results", [])]
    answer = data.get("answer")
    digest = _digest(items)
    return f"Answer: {answer}\n\nSources:\n{digest}" if answer else digest


def _brave(query: str, n: int) -> str:
    r = httpx.get(
        "https://api.search.brave.com/res/v1/web/search",
        params={"q": query, "count": n},
        headers={"X-Subscription-Token": settings.search_api_key, "Accept": "application/json"},
        timeout=30,
    )
    r.raise_for_status()
    web = r.json().get("web", {}).get("results", [])
    return _digest([(x.get("title", ""), x.get("url", ""), x.get("description", "")) for x in web])


def _serper(query: str, n: int) -> str:
    r = httpx.post(
        "https://google.serper.dev/search",
        json={"q": query, "num": n},
        headers={"X-API-KEY": settings.search_api_key, "Content-Type": "application/json"},
        timeout=30,
    )
    r.raise_for_status()
    organic = r.json().get("organic", [])
    return _digest([(x.get("title", ""), x.get("link", ""), x.get("snippet", "")) for x in organic])
