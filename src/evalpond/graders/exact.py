"""Exact-match grader: deterministic, no model calls. Scores per field."""
from __future__ import annotations

from typing import Any

from ..schema import GradeResult, GradeSpec
from . import normalize as N

DATE_KEYS = ("period_start", "period_end", "date")


def _kind(field: str, expected: Any) -> str:
    if isinstance(expected, bool):
        return "bool"
    if isinstance(expected, (int, float)):
        return "money"
    if isinstance(expected, list):
        if expected and isinstance(expected[0], dict):
            return "deposits"
        return "set"
    if field in DATE_KEYS:
        return "date"
    if field == "pay_frequency":
        return "frequency"
    return "name"


def _same(kind: str, expected: Any, got: Any, tol: float) -> bool:
    if expected is None:
        return N.is_abstain(got)  # reward abstaining, punish inventing
    if N.is_abstain(got):
        return kind == "set" and expected == []
    if kind == "bool":
        if isinstance(got, str):
            got = got.strip().lower() == "true"
        return bool(got) is expected
    if kind == "money":
        g = N.money(got)
        return g is not None and abs(g - float(expected)) <= tol
    if kind == "date":
        return N.date_iso(got) == expected
    if kind == "frequency":
        return N.frequency(got) == expected
    if kind == "set":
        if not isinstance(got, list):
            return False
        return {N.name(str(x)) for x in got} == {N.name(str(x)) for x in expected}
    if kind == "deposits":
        if not isinstance(got, list):
            return False
        try:
            g = sorted((N.date_iso(x["date"]) or "", round(N.money(x["amount"]) or 0, 2)) for x in got)
        except (KeyError, TypeError):
            return False
        e = sorted((x["date"], round(x["amount"], 2)) for x in expected)
        return len(g) == len(e) and all(a[0] == b[0] and abs(a[1] - b[1]) <= tol for a, b in zip(g, e))
    return N.name(got) == N.name(expected)


def grade_exact(spec: GradeSpec, expected: dict[str, Any], parsed: dict[str, Any] | None) -> GradeResult:
    parsed = parsed or {}
    details: dict[str, Any] = {}
    ok = 0
    for f in spec.fields:
        exp = expected[f]
        kind = _kind(f, exp if exp is not None else expected.get(f))
        if exp is None:  # kind for null expectations only matters for the abstain branch
            kind = "name"
        good = _same(kind, exp, parsed.get(f), spec.tolerance)
        ok += good
        details[f] = {"expected": exp, "got": parsed.get(f), "ok": good}
    score = ok / len(spec.fields) if spec.fields else 0.0
    return GradeResult(method="exact", score=score, weight=spec.weight,
                       details={"fields": details, "fields_correct": ok, "fields_total": len(spec.fields),
                                "all_correct": ok == len(spec.fields)})
