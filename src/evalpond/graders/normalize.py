"""Normalizers for exact-match grading. Deterministic, heavily unit-tested."""
from __future__ import annotations

import re
from datetime import datetime
from typing import Any

ABSTAIN = {"", "null", "none", "n/a", "na", "not present", "not stated", "not found", "not available",
           "cannot determine", "can't determine", "unknown", "not shown", "missing"}

_DATE_FORMATS = ["%Y-%m-%d", "%m/%d/%Y", "%b %d, %Y", "%B %d, %Y", "%d-%b-%y", "%d %b %Y", "%Y/%m/%d"]


def is_abstain(v: Any) -> bool:
    if v is None:
        return True
    return isinstance(v, str) and v.strip().lower() in ABSTAIN


def money(v: Any) -> float | None:
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str):
        s = re.sub(r"(?i)usd|\$|,|\s", "", v)
        neg = s.startswith("(") and s.endswith(")")
        s = s.strip("()")
        try:
            x = float(s)
        except ValueError:
            return None
        return -x if neg else x
    return None


def date_iso(v: Any) -> str | None:
    if not isinstance(v, str):
        return None
    s = v.strip()
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(s, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def name(v: Any) -> str | None:
    if not isinstance(v, str):
        return None
    s = re.sub(r"[^\w\s&-]", "", v.casefold())
    return re.sub(r"\s+", " ", s).strip()


def frequency(v: Any) -> str | None:
    if not isinstance(v, str):
        return None
    s = v.casefold().replace("_", "-").replace(" ", "-").strip()
    return {"bi-weekly": "biweekly", "semimonthly": "semi-monthly", "twice-monthly": "semi-monthly",
            "every-two-weeks": "biweekly", "fortnightly": "biweekly"}.get(s, s)
