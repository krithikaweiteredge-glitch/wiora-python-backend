"""Compute the next occurrence of a recurring item."""
from __future__ import annotations

from datetime import datetime, timedelta


def next_occurrence(dt: datetime, repeat: str) -> datetime | None:
    """Next datetime after `dt` for repeat in {daily, weekly, monthly}, else None."""
    if repeat == "daily":
        return dt + timedelta(days=1)
    if repeat == "weekly":
        return dt + timedelta(weeks=1)
    if repeat == "monthly":
        month = dt.month + 1
        year = dt.year + (month - 1) // 12
        month = (month - 1) % 12 + 1
        day = min(dt.day, 28)  # clamp to keep every month valid
        return dt.replace(year=year, month=month, day=day)
    return None
