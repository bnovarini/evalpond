"""Check a task set and add tasks to it, without hand-editing JSON.

`validate_taskset` answers "will the harness understand this, and can each task actually tell a right answer
from a wrong one?". `add_task` writes one task (and its document text) after the same checks pass.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from .grading import grade_task
from .models.mock import _corrupt, _rng
from .runner import answer_keys, load_tasks, prompt_text
from .schema import ModelOutput, RubricItem, Task

KNOWN_CHECKS = {"field_equals", "set_equals", "any_of", "none_of", "max_words", "numbers_subset", "mentions"}
FM_PREFIX = "fm:"
_PII = [
    ("an email address", re.compile(r"[\w.+-]+@(?!example\.(?:com|org|net)\b)[\w-]+\.[\w.-]+")),
    ("a US social security number", re.compile(r"\b\d{3}-\d{2}-\d{4}\b")),
    ("a phone number", re.compile(r"\b(?!555[-. ]01\d\d)\(?\d{3}\)?[-. ]\d{3}[-. ]\d{4}\b(?<!555-0100)")),
    ("a long account or card number", re.compile(r"\b\d{12,19}\b")),
]


def _issue(level: str, task: str, code: str, message: str) -> dict[str, str]:
    return {"level": level, "task": task, "code": code, "message": message}


def slugify(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:40] or "task"


def failure_mode(task: Task) -> str:
    return next((t[len(FM_PREFIX):] for t in task.tags if t.startswith(FM_PREFIX)), "")


def severity(task: Task) -> str:
    return next((t[4:] for t in task.tags if t.startswith("sev:")), "")


def _doc_text(taskset: Path, task: Task) -> str:
    out = []
    for p in task.text_documents:
        f = taskset / p
        if f.exists():
            out.append(f.read_text(errors="ignore"))
    return "\n".join(out)


def _gold_output(task: Task) -> ModelOutput | None:
    """A perfect answer built from the answer key, or None if a model is needed to judge it."""
    gold = {k: v for k, v in task.expected.items() if k not in ("allowed_numbers", "mock_variants")}
    words: list[str] = []
    for spec in task.grading:
        if spec.method == "judge":
            return None
        if spec.method == "rubric":
            for it in spec.rubric:
                kind, _, arg = it.check.partition(":")
                if not it.check or kind not in KNOWN_CHECKS:
                    return None
                if kind == "mentions":
                    words.append(arg)
                elif kind == "any_of":
                    words.append(arg.split("|")[0])
                elif kind == "field_equals":
                    key, _, want = arg.partition("=")
                    gold[key] = {"true": True, "false": False}.get(want, want)
    if words or not any(s.method == "exact" for s in task.grading):
        gold.setdefault("answer", " ".join(words))
    return ModelOutput(text=json.dumps(gold), parsed=gold)


def _wrong_output(task: Task) -> ModelOutput:
    """A plausible wrong answer: every exact field corrupted, free text emptied."""
    rng = _rng("validate", task.id)
    wrong: dict[str, Any] = {}
    for spec in task.grading:
        for f in spec.fields:
            v = task.expected.get(f)
            wrong[f] = "Unknown Corp" if v is None else _corrupt(v, rng)
    wrong["answer"] = ""
    return ModelOutput(text=json.dumps(wrong), parsed=wrong)


def check_task(task: Task, taskset: Path) -> list[dict[str, str]]:
    """All problems with one task: errors block a run, warnings are worth reading."""
    tid, out = task.id, []
    for p in task.documents + task.text_documents:
        if not (taskset / p).exists():
            out.append(_issue("error", tid, "missing_document", f"The file {p} does not exist."))
    try:
        tpl = prompt_text(task.prompt_template, taskset)
        if (task.documents or task.text_documents) and "{{documents}}" not in tpl:
            out.append(_issue("error", tid, "prompt_no_documents", f"Prompt '{task.prompt_template}' has no {{{{documents}}}} slot, so the model would never see the document."))
        if "{{question}}" in tpl and not task.question:
            out.append(_issue("error", tid, "no_question", "This prompt asks for a question, but the task has none."))
    except FileNotFoundError:
        out.append(_issue("error", tid, "prompt_missing", f"No prompt named '{task.prompt_template}'. Built-in: generic_v1, or add prompts/{task.prompt_template}.txt to the task set."))
    if not task.expected:
        out.append(_issue("error", tid, "no_expected", "There is no right answer written down (expected is empty)."))
    if not task.grading:
        out.append(_issue("error", tid, "no_grading", "There is no way to grade this task. Add an exact, rubric or judge grader."))
    for i, spec in enumerate(task.grading):
        if spec.weight <= 0:
            out.append(_issue("error", tid, "bad_weight", f"Grader {i + 1} has a weight of zero or less."))
        if spec.method == "exact":
            if not spec.fields:
                out.append(_issue("error", tid, "exact_no_fields", "An exact grader needs at least one field to compare."))
            for f in spec.fields:
                if f not in task.expected:
                    out.append(_issue("error", tid, "exact_field_unknown", f"The grader compares '{f}', but the right answer has no '{f}'."))
        elif spec.method == "rubric":
            if not spec.rubric:
                out.append(_issue("error", tid, "rubric_empty", "A rubric grader needs at least one yes/no criterion."))
            ids = [r.id for r in spec.rubric]
            if len(set(ids)) != len(ids):
                out.append(_issue("error", tid, "rubric_dup", "Two rubric criteria share an id."))
            for r in spec.rubric:
                kind, _, arg = r.check.partition(":")
                if r.check and kind not in KNOWN_CHECKS:
                    out.append(_issue("error", tid, "check_unknown", f"Criterion '{r.id}' uses an unknown check '{kind}'. Known: {', '.join(sorted(KNOWN_CHECKS))}."))
                elif r.check and not arg:
                    out.append(_issue("error", tid, "check_empty", f"Criterion '{r.id}' has a check with nothing to check for."))
                elif kind == "field_equals" and "=" not in arg:
                    out.append(_issue("error", tid, "check_format", f"Criterion '{r.id}': field_equals needs key=value."))
                elif kind == "max_words" and not arg.isdigit():
                    out.append(_issue("error", tid, "check_format", f"Criterion '{r.id}': max_words needs a number."))
        elif spec.method == "judge" and not spec.judge_question:
            out.append(_issue("error", tid, "judge_no_question", "A judge grader needs a question for the AI grader."))
    text = _doc_text(taskset, task)
    for label, rx in _PII:
        if rx.search(text) or rx.search(task.question) or rx.search(json.dumps(task.expected)):
            out.append(_issue("error", tid, "pii", f"This task seems to contain {label}. Use made-up examples only (see NOTICE.md)."))
    if any(e["level"] == "error" for e in out):
        return out
    # does the answer key appear in the material? (a typo in the key is the most common silent mistake)
    if text:
        low = text.lower()
        for spec in task.grading:
            for f in spec.fields if spec.method == "exact" else []:
                v = task.expected.get(f)
                if isinstance(v, str) and v.strip() and v.lower() not in low:
                    out.append(_issue("warning", tid, "key_not_in_document", f"Expected {f} = '{v}' does not appear in the document text. Fine if the model must work it out; otherwise check for a typo."))
                if isinstance(v, (int, float)) and not isinstance(v, bool):
                    forms = {f"{v:,.2f}", f"{v:.2f}", f"{v:,}", str(v), f"{v:,.0f}"}
                    if not any(x in text for x in forms):
                        out.append(_issue("warning", tid, "key_not_in_document", f"Expected {f} = {v} does not appear in the document text. Fine if the model must work it out; otherwise check for a typo."))
    gold = _gold_output(task)
    if gold is None:
        out.append(_issue("info", tid, "needs_judge", "Graded by an AI grader, so the answer key could not be self-tested. Run with --judge and hand-check a few."))
    else:
        _, score, passed = grade_task(task, gold, None)
        if not passed:
            out.append(_issue("error", tid, "gold_fails", f"A perfect answer built from the answer key scores {score:.0%}. The key and the grader disagree."))
        _, _, wpassed = grade_task(task, _wrong_output(task), None)
        if wpassed:
            out.append(_issue("warning", tid, "cannot_fail", "A deliberately wrong answer still passes. Add a check that a wrong answer would miss."))
    return out


def validate_taskset(taskset: Path) -> dict[str, Any]:
    """Validate a whole task set. Returns a plain dict, ready for printing or --json."""
    issues: list[dict[str, str]] = []
    path = taskset / "tasks.jsonl"
    if not path.exists():
        return {"taskset": str(taskset), "ok": False, "tasks": 0, "errors": [_issue("error", "", "no_tasks_file", f"{path} not found.")], "warnings": [], "info": [], "summary": {}}
    if not (taskset / "manifest.yaml").exists():
        issues.append(_issue("error", "", "no_manifest", "manifest.yaml is missing. `evalpond add-task` creates it."))
    tasks: list[Task] = []
    for n, line in enumerate(path.read_text().splitlines(), 1):
        if not line.strip():
            continue
        try:
            tasks.append(Task(**json.loads(line)))
        except (json.JSONDecodeError, ValidationError, TypeError) as e:
            first = str(e).splitlines()[0] if str(e) else type(e).__name__
            issues.append(_issue("error", f"line {n}", "bad_task", f"Line {n} is not a valid task: {first}"))
    seen: set[str] = set()
    for t in tasks:
        if t.id in seen:
            issues.append(_issue("error", t.id, "dup_id", f"The id '{t.id}' is used twice."))
        seen.add(t.id)
        issues += check_task(t, taskset)
    n = len(tasks)
    cats: dict[str, int] = {}
    for t in tasks:
        cats[t.category] = cats.get(t.category, 0) + 1
    not_present = sum(1 for t in tasks if any(v is None for v in t.expected.values()))
    test_n = sum(1 for t in tasks if t.split == "test")
    judge_n = sum(1 for t in tasks if any(g.method == "judge" or (g.method == "rubric" and any(not r.check for r in g.rubric)) for g in t.grading))
    if n:
        if n < 20:
            issues.append(_issue("warning", "", "small_set", f"Only {n} tasks. That is enough to find problems, not to tell two similar models apart. Aim for 30 or more per failure mode you care about."))
        if n >= 10 and not_present / n < 0.10:
            issues.append(_issue("warning", "", "few_not_present", "Very few tasks where the right answer is 'the document does not say'. Models that make things up will look better than they are."))
        if n >= 10 and test_n == 0:
            issues.append(_issue("warning", "", "no_test_split", "No tasks are marked split=test. Keep about 20% aside and do not tune on them."))
        for c, k in cats.items():
            if k < 3:
                issues.append(_issue("warning", "", "thin_category", f"Failure mode '{c}' has only {k} task(s). One or two tasks cannot show a pattern."))
        if judge_n == n:
            issues.append(_issue("warning", "", "all_judged", "Every task needs an AI grader. Prefer exact or rubric checks where you can; they cost nothing and do not drift."))
    errs = [i for i in issues if i["level"] == "error"]
    summary = {"tasks": n, "by_category": cats, "not_present": not_present, "test_split": test_n,
               "ai_graded": judge_n, "self_tested": sum(1 for t in tasks if _gold_output(t) is not None)}
    return {"taskset": str(taskset), "ok": not errs, "tasks": n, "summary": summary, "errors": errs,
            "warnings": [i for i in issues if i["level"] == "warning"], "info": [i for i in issues if i["level"] == "info"]}


def render_validation(rep: dict[str, Any]) -> str:
    s = rep.get("summary", {})
    lines = []
    if rep["ok"]:
        lines.append(f"{rep['taskset']}: {rep['tasks']} tasks, ready to run.")
    else:
        lines.append(f"{rep['taskset']}: NOT ready. {len(rep['errors'])} problem(s) must be fixed first.")
    for i in rep["errors"]:
        lines.append(f"  ERROR   {i['task'] or '(set)'}: {i['message']}")
    for i in rep["warnings"]:
        lines.append(f"  warning {i['task'] or '(set)'}: {i['message']}")
    for i in rep["info"][:5]:
        lines.append(f"  note    {i['task']}: {i['message']}")
    if len(rep["info"]) > 5:
        lines.append(f"  note    ...and {len(rep['info']) - 5} more AI-graded tasks")
    if s:
        lines.append(f"  {s['self_tested']} of {s['tasks']} tasks were self-tested (a right answer passes, a wrong one fails).")
    return "\n".join(lines)


def _refresh_manifest(taskset: Path, titles: dict[str, str]) -> None:
    tasks = load_tasks(taskset)
    mpath = taskset / "manifest.yaml"
    m = yaml.safe_load(mpath.read_text()) if mpath.exists() else {}
    m.setdefault("name", taskset.name)
    m.setdefault("generator_version", "user")
    m.setdefault("seed", 0)
    m.setdefault("synthetic", True)
    m.setdefault("note", "Hand-written task set. Every document is made up. See NOTICE.md.")
    m["task_count"] = len(tasks)
    m["by_category"] = dict(sorted({c: sum(t.category == c for t in tasks) for c in {t.category for t in tasks}}.items()))
    m["by_difficulty"] = {d: sum(t.difficulty == d for t in tasks) for d in ("easy", "medium", "hard") if any(t.difficulty == d for t in tasks)}
    m["by_split"] = {s: sum(t.split == s for t in tasks) for s in ("dev", "test") if any(t.split == s for t in tasks)}
    m["not_present_tasks"] = sum(1 for t in tasks if any(v is None for v in t.expected.values()))
    m["categories"] = {**m.get("categories", {}), **titles}
    mpath.write_text(yaml.safe_dump(m, sort_keys=True))


def add_task(taskset: Path, spec: dict[str, Any], inputs: list[str], *, dry_run: bool = False) -> dict[str, Any]:
    """Write one task. `spec` holds Task fields; `inputs` are the document texts. Refuses when the checks find errors."""
    taskset.mkdir(parents=True, exist_ok=True)
    existing = load_tasks(taskset) if (taskset / "tasks.jsonl").exists() else []
    fm = spec.pop("failure_mode", "") or ""
    spec = dict(spec)
    if fm:
        spec["tags"] = [*spec.get("tags", []), FM_PREFIX + slugify(fm)] if FM_PREFIX + slugify(fm) not in spec.get("tags", []) else spec.get("tags", [])
        spec.setdefault("category", slugify(fm))
    spec.setdefault("category", "general")
    if not spec.get("id"):
        base = slugify(fm or spec["category"])
        k = 1 + sum(t.id.startswith(base + "-") for t in existing)
        spec["id"] = f"{base}-{k:02d}"
    spec.setdefault("difficulty", "medium")
    spec.setdefault("split", "dev")
    spec.setdefault("prompt_template", "generic_v1")
    spec.setdefault("grading", [])
    spec.setdefault("plain_title", fm or spec["id"])
    spec["text_documents"] = [f"docs/{spec['id']}-{i}.txt" for i in range(1, len(inputs) + 1)]
    if any(t.id == spec["id"] for t in existing):
        return {"ok": False, "id": spec["id"], "errors": [_issue("error", spec["id"], "dup_id", f"The id '{spec['id']}' already exists.")], "warnings": []}
    try:
        task = Task(**spec)
    except ValidationError as e:
        return {"ok": False, "id": spec["id"], "errors": [_issue("error", spec["id"], "bad_task", str(e).splitlines()[0])], "warnings": []}
    # write the documents first so the file checks see them; roll back on failure
    written: list[Path] = []
    for rel, text in zip(task.text_documents, inputs):
        f = taskset / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(text.rstrip("\n") + "\n")
        written.append(f)
    issues = check_task(task, taskset)
    errors = [i for i in issues if i["level"] == "error"]
    if errors or dry_run:
        for f in written:
            f.unlink(missing_ok=True)
        return {"ok": not errors, "id": task.id, "written": False, "errors": errors,
                "warnings": [i for i in issues if i["level"] != "error"], "task": task.model_dump()}
    with (taskset / "tasks.jsonl").open("a") as fh:
        fh.write(json.dumps(task.model_dump(), ensure_ascii=False, sort_keys=True) + "\n")
    _refresh_manifest(taskset, {task.category: fm or task.category} if fm else {})
    return {"ok": True, "id": task.id, "written": True, "errors": [], "warnings": [i for i in issues if i["level"] != "error"],
            "path": str(taskset / "tasks.jsonl"), "keys_asked": answer_keys(task)}


def rubric_from_flags(items: list[str]) -> list[RubricItem]:
    """--check 'id|text|check'. The check part is optional (no check means the AI grader answers it)."""
    out = []
    for raw in items:
        parts = [p.strip() for p in raw.split("|")]
        if len(parts) < 2:
            raise ValueError(f"--check needs 'id|plain-language criterion|check', got: {raw}")
        out.append(RubricItem(id=parts[0], text=parts[1], check=parts[2] if len(parts) > 2 else ""))
    return out
