"""Builds the static report: one self-contained HTML file with the data embedded. No backend."""
from __future__ import annotations

import json
import math
from importlib import resources
from itertools import permutations
from pathlib import Path

import yaml

from .. import stats
from ..calibrate import load_labels
from ..runner import load_tasks
from ..schema import Run
from . import copy as C

CATEGORY_NAMES = {"A": "Read pay stubs", "B": "Read bank statements", "C": "Work out monthly income",
                  "D": "Check the package is complete", "E": "Spot contradictions"}


def _rate(k: int, n: int) -> dict:
    lo, hi = stats.wilson(k, n)
    return {"k": k, "n": n, "rate": k / n if n else 0, "lo": lo, "hi": hi}


def _group(run: Run, key) -> dict:
    out: dict[str, list[bool]] = {}
    for r in run.results:
        out.setdefault(key(r), []).append(r.passed)
    return {g: _rate(sum(v), len(v)) for g, v in sorted(out.items())}


def run_summary(run: Run, tasks: dict) -> dict:
    n = len(run.results)
    k = sum(r.passed for r in run.results)
    lat = [r.output.latency_s for r in run.results]
    judge_rows = [(g.details.get("answer_chars", 0), g.score) for r in run.results for g in r.grades if g.method == "judge"]
    return {
        "overall": _rate(k, n),
        "avg_score": sum(r.score for r in run.results) / n if n else 0,
        "by_category": _group(run, lambda r: tasks[r.task_id].category),
        "by_difficulty": _group(run, lambda r: tasks[r.task_id].difficulty),
        "by_split": _group(run, lambda r: tasks[r.task_id].split),
        "flaky": stats.flaky_tasks(run),
        "cost": run.total_cost_usd,
        "latency": sum(lat) / len(lat) if lat else 0,
        "errors": sum(1 for r in run.results if r.output.error),
        "length_corr": stats.pearson([float(x) for x, _ in judge_rows], [s for _, s in judge_rows]) if judge_rows else None,
    }


def judge_health(runs: list[Run], labels: list[dict]) -> dict:
    by_answer = {x["answer"]: x for x in labels}
    pairs = []
    for run in runs:
        for r in run.results:
            for g in r.grades:
                if g.method == "judge" and g.details.get("answer") in by_answer:
                    pairs.append((by_answer[g.details["answer"]]["human"], int(g.score)))
    if not pairs:
        return {"labeled": 0}
    h, j = [p[0] for p in pairs], [p[1] for p in pairs]
    return {"labeled": len(pairs), "agree": sum(a == b for a, b in pairs), "chance_adjusted": stats.cohen_kappa(h, j)}


def _sanitize(v):
    """JSON has no NaN. Turn NaN into null, recursively."""
    if isinstance(v, float) and math.isnan(v):
        return None
    if isinstance(v, dict):
        return {k: _sanitize(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [_sanitize(x) for x in v]
    return v


def build_data(runs_dir: Path, taskset_dir: Path, labels_path: Path | None = None, title: str = "evalpond report") -> dict:
    runs = [Run(**json.loads(p.read_text())) for p in sorted(runs_dir.glob("*.json"))]
    runs = [r for r in runs if r.results]
    task_list = load_tasks(taskset_dir)
    tasks = {t.id: t for t in task_list}
    manifest = yaml.safe_load((taskset_dir / "manifest.yaml").read_text())
    data: dict = {"title": title, "manifest": manifest, "categories": CATEGORY_NAMES, "copy": {"plain": C.PLAIN, "details": C.DETAILS}}
    data["tasks"] = [{
        "id": t.id, "category": t.category, "difficulty": t.difficulty, "split": t.split, "title": t.plain_title,
        "why": t.why_it_matters, "good": t.what_good_looks_like, "tags": t.tags, "expected": t.expected,
        "docs": [(taskset_dir / p).read_text() for p in t.text_documents]} for t in task_list]
    data["runs"] = []
    for run in runs:
        data["runs"].append({
            "id": run.run_id, "label": run.label or run.run_id, "model": run.model.name, "judge": run.judge_model,
            "git": run.git_sha, "started": run.started_at, "repeats": run.repeats, "version": run.taskset_version,
            "prompts": run.prompt_hashes, "summary": run_summary(run, tasks),
            "results": [{"t": r.task_id, "r": r.repeat, "p": int(r.passed), "s": r.score, "err": r.output.error,
                         "mode": r.output.doc_mode, "out": r.output.parsed if r.output.parsed is not None else r.output.text,
                         "g": [{"m": g.method, "s": g.score, "d": g.details} for g in r.grades]} for r in run.results]})
    data["compare"] = {}
    for a, b in permutations(runs, 2):
        c = stats.compare_runs(a, b)
        la, lb = a.label or a.run_id, b.label or b.run_id
        data["compare"][f"{a.run_id}|{b.run_id}"] = {
            "n": c.n, "fixed": c.fixed, "regressed": c.regressed, "same_right": c.unchanged_pass, "same_wrong": c.unchanged_fail,
            "p": c.p_value, "verdict": c.verdict, "mean_diff": c.mean_diff, "diff_ci": list(c.diff_ci),
            "pass_a": c.pass_a, "pass_b": c.pass_b, "min_gap": c.min_gap, "notes": c.notes,
            "sentence": C.compare_sentence(la, lb, c), "advice": C.advice(c, la, lb, c.regressed)}
    data["judge_health"] = judge_health(runs, load_labels(labels_path) if labels_path else [])
    return _sanitize(data)


def build_report(runs_dir: Path, taskset_dir: Path, out_dir: Path, labels_path: Path | None = None,
                 title: str = "evalpond report") -> Path:
    data = build_data(runs_dir, taskset_dir, labels_path, title)
    pkg = resources.files("evalpond.report")
    html = pkg.joinpath("template.html").read_text()
    css = pkg.joinpath("style.css").read_text()
    js = pkg.joinpath("app.js").read_text()
    payload = json.dumps(data, separators=(",", ":"), allow_nan=False).replace("</", "<\\/")
    html = (html.replace("/*CSS*/", css).replace("/*JS*/", js).replace("/*DATA*/", payload)
            .replace("{{TITLE}}", title))
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "index.html"
    path.write_text(html)
    return path
