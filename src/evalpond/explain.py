"""Turn one run into a structured, plain-language explanation. `evalpond explain RUN --json` feeds agents; text is for people."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from . import stats
from .graders import normalize as N
from .runner import load_tasks
from .schema import Run, Task, TaskResult
from .taskkit import failure_mode, severity


def _what_failed(r: TaskResult, task: Task | None) -> list[dict[str, Any]]:
    """One entry per thing that went wrong in a failed answer."""
    out: list[dict[str, Any]] = []
    if r.output.error:
        return [{"kind": "model_error", "detail": r.output.error[:200]}]
    for g in r.grades:
        d = g.details
        if "error" in d:
            out.append({"kind": "unreadable_answer", "detail": str(d["error"])[:200]})
        elif g.method == "exact":
            for f, v in d.get("fields", {}).items():
                if v["ok"]:
                    continue
                kind = "made_something_up" if v["expected"] is None and not N.is_abstain(v["got"]) else (
                    "missed_a_value" if N.is_abstain(v["got"]) else "wrong_value")
                out.append({"kind": kind, "field": f, "expected": v["expected"], "got": v["got"]})
        elif g.method == "rubric":
            for cid, c in d.get("criteria", {}).items():
                if not c["met"]:
                    out.append({"kind": "missed_criterion", "criterion": cid, "text": c["text"], "how_checked": c["how"]})
        elif g.method == "judge" and g.score < 1:
            out.append({"kind": "judge_said_no", "detail": str(d.get("reasoning", ""))[:200], "answer": str(d.get("answer", ""))[:300]})
    return out


PATTERN_TEXT = {
    "made_something_up": "Invented an answer where the document does not say",
    "missed_a_value": "Said it could not find something that was there",
    "wrong_value": "Found the field but got the value wrong",
    "missed_criterion": "Left out or broke a required part of the answer",
    "judge_said_no": "The AI grader judged the answer not good enough",
    "unreadable_answer": "Did not return an answer in the requested format",
    "model_error": "The model call itself failed (not a quality problem)",
}


def explain_run(run: Run, taskset: Path | None, *, top: int = 8) -> dict[str, Any]:
    tasks: dict[str, Task] = {}
    if taskset and (taskset / "tasks.jsonl").exists():
        tasks = {t.id: t for t in load_tasks(taskset)}
    n = len(run.results)
    k = sum(r.passed for r in run.results)
    lo, hi = stats.wilson(k, n)
    cat_title: dict[str, str] = {}
    if taskset and (taskset / "manifest.yaml").exists():
        import yaml
        cat_title = (yaml.safe_load((taskset / "manifest.yaml").read_text()) or {}).get("categories", {}) or {}

    def key_cat(r: TaskResult) -> str:
        t = tasks.get(r.task_id)
        return t.category if t else "(unknown)"

    by_cat = []
    for c, rs in sorted(stats.results_by(run, key_cat).items()):
        kk = sum(x.passed for x in rs)
        by_cat.append({"category": c, "title": cat_title.get(c, c), "answers": len(rs), "correct": kk, "rate": round(kk / len(rs), 3)})
    fix_first: dict[str, dict[str, Any]] = {}
    patterns: dict[str, dict[str, Any]] = {}
    failures = []
    for r in sorted(run.results, key=lambda x: (x.score, x.task_id)):
        if r.passed:
            continue
        t = tasks.get(r.task_id)
        wf = _what_failed(r, t)
        for w in wf:
            p = patterns.setdefault(w["kind"], {"kind": w["kind"], "meaning": PATTERN_TEXT.get(w["kind"], w["kind"]), "count": 0, "task_ids": []})
            p["count"] += 1
            if r.task_id not in p["task_ids"]:
                p["task_ids"].append(r.task_id)
        fm = failure_mode(t) if t else ""
        if t and fm:
            row = fix_first.setdefault(fm, {"failure_mode": fm, "severity": severity(t) or "unrated", "failed": 0, "task_ids": []})
            row["failed"] += 1
            row["task_ids"].append(r.task_id)
        failures.append({"task_id": r.task_id, "repeat": r.repeat, "title": t.plain_title if t else "", "category": key_cat(r),
                         "failure_mode": failure_mode(t) if t else "", "score": r.score, "what_failed": wf})
    for p in patterns.values():
        p["task_ids"] = p["task_ids"][:10]
    errors = sum(1 for r in run.results if r.output.error)
    tp = stats.task_passes(run)
    flaky = stats.flaky_tasks(run)
    n_tasks = len(tp)
    caveats: list[str] = []
    if n < 30:
        caveats.append(f"Only {n} answers. Treat the pass rate as a rough read: the real rate could be anywhere from {lo * 100:.0f}% to {hi * 100:.0f}%.")
    if errors:
        caveats.append(f"{errors} of {n} answers failed because the model call errored. Fix that before trusting the score.")
    if run.judge_model:
        caveats.append(f"Some answers were graded by an AI ({run.judge_model}). Hand-check a few with `evalpond calibrate`.")
    if run.repeats == 1 and n_tasks:
        caveats.append("Each task ran once. A single run can swing; use --repeats 3 before trusting a small difference.")
    if tasks and any(t.split == "test" for t in tasks.values()) and "test" in {tasks[r.task_id].split for r in run.results if r.task_id in tasks}:
        splits = {tasks[r.task_id].split for r in run.results if r.task_id in tasks}
        if splits == {"dev", "test"}:
            caveats.append("This run mixes dev and test tasks. Tune on dev only; read the test tasks once at the end.")
    next_steps: list[str] = []
    top_pat = sorted(patterns.values(), key=lambda p: -p["count"])
    if errors:
        next_steps.append("Fix the model errors (key, model name, rate limit), then re-run. Finished answers are kept.")
    if top_pat and top_pat[0]["kind"] != "model_error":
        next_steps.append(f"Biggest pattern: {top_pat[0]['meaning'].lower()} ({top_pat[0]['count']}). Read those answers first: `evalpond explain` lists them.")
    if not failures and n:
        next_steps.append("Everything passed. Either the tasks are too easy or the model is good here. Add harder tasks for the failure modes you worry about.")
    return {
        "run_id": run.run_id, "model": run.model.name, "taskset": run.taskset, "judge_model": run.judge_model,
        "answers": n, "tasks": n_tasks, "repeats": run.repeats, "fully_correct": k,
        "pass_rate": round(k / n, 3) if n else 0.0, "pass_rate_range": [round(lo, 3), round(hi, 3)],
        "avg_score": round(sum(r.score for r in run.results) / n, 3) if n else 0.0,
        "cost_usd": run.total_cost_usd, "model_errors": errors, "flaky_tasks": flaky,
        "by_category": by_cat, "patterns": top_pat, "failures": failures[:top], "failures_total": len(failures),
        "fix_first": sorted(fix_first.values(), key=lambda x: ({"high": 0, "medium": 1, "unrated": 2, "low": 3}[x["severity"]], -x["failed"])),
        "caveats": caveats, "next_steps": next_steps,
    }


def render_explanation(e: dict[str, Any]) -> str:
    lo, hi = e["pass_rate_range"]
    lines = [f"{e['model']} on {e['taskset']}: {e['fully_correct']} of {e['answers']} answers completely right ({e['pass_rate'] * 100:.0f}%).",
             f"  Plausible range given this many tasks: {lo * 100:.0f}% to {hi * 100:.0f}%.  Cost: ${e['cost_usd']:.2f}."]
    if len(e["by_category"]) > 1:
        lines.append("\nBy area:")
        for c in e["by_category"]:
            lines.append(f"  {c['title']}: {c['correct']}/{c['answers']} ({c['rate'] * 100:.0f}%)")
    if e["fix_first"]:
        lines.append("\nFix first (your severity ratings, then how often it failed):")
        for f in e["fix_first"][:5]:
            lines.append(f"  {f['failure_mode']} [{f['severity']}]: {f['failed']} failed answer(s)")
    if e["patterns"]:
        lines.append("\nWhat went wrong, most common first:")
        for p in e["patterns"]:
            lines.append(f"  {p['count']}x  {p['meaning']}  (e.g. {', '.join(p['task_ids'][:3])})")
    if e["failures"]:
        lines.append(f"\nWeakest answers ({len(e['failures'])} of {e['failures_total']} shown):")
        for f in e["failures"]:
            w = f["what_failed"][0] if f["what_failed"] else {}
            bit = (f"{w.get('field')}: expected {w.get('expected')!r}, got {w.get('got')!r}" if "field" in w
                   else w.get("text") or w.get("detail", ""))
            lines.append(f"  {f['task_id']}: {bit}")
    for c in e["caveats"]:
        lines.append(f"\nCaution: {c}")
    for s in e["next_steps"]:
        lines.append(f"Next: {s}")
    return "\n".join(lines)
