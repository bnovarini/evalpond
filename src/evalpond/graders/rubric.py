"""Rubric grader: a list of yes/no criteria with weights. Programmatic checks first, judge for the rest."""
from __future__ import annotations

import re

from ..schema import GradeResult, GradeSpec, RubricItem, Task
from . import normalize as N
from .judge import candidate_text


def _field_equals(check: str, parsed: dict) -> bool:
    key, _, want = check.partition("=")
    got = parsed.get(key)
    if want in ("true", "false"):
        if isinstance(got, str):
            got = got.strip().lower() == "true"
        return isinstance(got, bool) and got is (want == "true")
    if key == "pay_frequency":
        return N.frequency(got) == want
    return str(got).strip().lower() == want.lower()


def _set_equals(key: str, parsed: dict, expected: dict) -> bool:
    got = parsed.get(key)
    return isinstance(got, list) and {str(x).casefold() for x in got} == {str(x).casefold() for x in expected[key]}


def check_item(item: RubricItem, task: Task, out, judge) -> tuple[bool, str]:
    parsed = out.parsed or {}
    kind, _, arg = item.check.partition(":")
    if kind == "field_equals":
        return _field_equals(arg, parsed), "programmatic"
    if kind == "set_equals":
        return _set_equals(arg, parsed, task.expected), "programmatic"
    if kind == "any_of":
        low = candidate_text(task, out).lower()
        return any(t.strip().lower() in low for t in arg.split("|") if t.strip()), "programmatic"
    if kind == "none_of":
        low = candidate_text(task, out).lower()
        return not any(t.strip().lower() in low for t in arg.split("|") if t.strip()), "programmatic"
    if kind == "max_words":
        return len(candidate_text(task, out).split()) <= int(arg), "programmatic"
    if kind == "numbers_subset":
        # every number in the answer must appear in the document's current requirements; small whole numbers are ignored
        allowed = {str(x) for x in task.expected.get("allowed_numbers", [])}
        used = set(re.findall(r"\d+(?:\.\d+)?", candidate_text(task, out).replace(",", "")))
        return all(n in allowed or (n.isdigit() and int(n) <= 10) for n in used), "programmatic"
    if kind == "mentions":
        return arg.lower() in candidate_text(task, out).lower(), "programmatic"
    if judge is None:
        raise RuntimeError(f"Task {task.id} needs an AI grader. Re-run with --judge <model name>.")
    spec = next((g for g in task.grading if g.method == "rubric"), None)
    kws = spec.judge_keywords if spec else []
    score, reasoning = judge.ask(item.text, arg, candidate_text(task, out), kws)
    return bool(score), reasoning


def grade_rubric(spec: GradeSpec, task: Task, out, judge) -> GradeResult:
    total = sum(i.weight for i in spec.rubric) or 1.0
    got, items = 0.0, {}
    for item in spec.rubric:
        ok, how = check_item(item, task, out, judge)
        got += item.weight if ok else 0
        items[item.id] = {"text": item.text, "met": ok, "how": how, "weight": item.weight}
    return GradeResult(method="rubric", score=round(got / total, 4), weight=spec.weight, details={"criteria": items})
