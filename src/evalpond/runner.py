"""Loads a task set, calls a model, grades answers, and saves one JSON file per run."""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from importlib import resources
from pathlib import Path
from typing import Any

import yaml

from .grading import grade_task
from .models.base import ModelAdapter, build_adapter
from .schema import DocumentRef, ModelConfig, ModelOutput, Run, Task, TaskResult


class CostCapExceeded(RuntimeError):
    pass


def load_tasks(taskset_dir: Path) -> list[Task]:
    path = taskset_dir / "tasks.jsonl"
    if not path.exists():
        raise FileNotFoundError(f"{path} not found. Run `evalpond gen` first.")
    return [Task(**json.loads(line)) for line in path.read_text().splitlines() if line.strip()]


def load_models(path: Path) -> dict[str, ModelConfig]:
    data = yaml.safe_load(path.read_text())
    return {m["name"]: ModelConfig(**m) for m in data["models"]}


def prompt_text(name: str, taskset_dir: Path | None = None) -> str:
    """A task set can ship its own prompts in <taskset>/prompts/NAME.txt; otherwise the built-in ones are used."""
    if taskset_dir is not None and (taskset_dir / "prompts" / f"{name}.txt").exists():
        return (taskset_dir / "prompts" / f"{name}.txt").read_text()
    return resources.files("evalpond").joinpath("prompts", f"{name}.txt").read_text()


def prompt_hash(name: str, taskset_dir: Path | None = None) -> str:
    return hashlib.sha256(prompt_text(name, taskset_dir).encode()).hexdigest()[:12]


def answer_keys(task: Task) -> str:
    """The JSON keys a model is asked for: the exact-graded fields, or one free-text `answer`."""
    fields = [f for g in task.grading if g.method == "exact" for f in g.fields]
    return ", ".join(dict.fromkeys(fields)) if fields else 'answer (a string)'


def build_prompt(task: Task, taskset_dir: Path, native: bool) -> tuple[str, DocumentRef]:
    texts = [(taskset_dir / p).read_text() for p in task.text_documents]
    if native:
        block = "The documents are attached."
    else:
        block = "\n\n".join(f"=== Document {i + 1} ===\n{t}" for i, t in enumerate(texts))
    prompt = (prompt_text(task.prompt_template, taskset_dir).replace("{{documents}}", block)
              .replace("{{question}}", task.question).replace("{{keys}}", answer_keys(task)))
    ref = DocumentRef(pdf_paths=[str(taskset_dir / p) for p in task.documents],
                      text="\n\n".join(texts), prefer_native=native, task_id=task.id, oracle=task.expected)
    return prompt, ref


def parse_json(text: str) -> dict[str, Any] | None:
    s = text.strip()
    s = re.sub(r"^```(?:json)?|```$", "", s, flags=re.MULTILINE).strip()
    try:
        v = json.loads(s)
        return v if isinstance(v, dict) else None
    except json.JSONDecodeError:
        pass
    m = re.search(r"\{.*\}", s, flags=re.DOTALL)
    if m:
        try:
            v = json.loads(m.group(0))
            return v if isinstance(v, dict) else None
        except json.JSONDecodeError:
            return None
    return None


def call_with_retries(adapter: ModelAdapter, prompt: str, ref: DocumentRef, retries: int = 3,
                      backoff: float = 1.5) -> ModelOutput:
    out = ModelOutput(error="not run")
    for attempt in range(retries + 1):
        t0 = time.time()
        try:
            out = adapter.run(prompt, ref)
        except Exception as e:  # noqa: BLE001 - adapters may raise anything
            out = ModelOutput(error=f"{type(e).__name__}: {e}")
        out.latency_s = out.latency_s or round(time.time() - t0, 3)
        if not out.error:
            break
        time.sleep(backoff ** attempt * 0.2)
    if out.parsed is None and out.text:
        out.parsed = parse_json(out.text)
    return out


def git_sha() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True,
                              timeout=5).stdout.strip()
    except Exception:  # noqa: BLE001
        return ""


def run_taskset(taskset_dir: Path, cfg: ModelConfig, *, run_id: str, out_dir: Path, repeats: int = 1,
                categories: set[str] | None = None, splits: set[str] | None = None, concurrency: int = 4,
                cost_cap: float | None = None, judge: Any | None = None, label: str = "",
                native: bool = False, resume: bool = True, progress=None) -> Run:
    tasks = [t for t in load_tasks(taskset_dir)
             if (not categories or t.category in categories) and (not splits or t.split in splits)]
    manifest = yaml.safe_load((taskset_dir / "manifest.yaml").read_text())
    out_path = out_dir / f"{run_id}.json"
    out_dir.mkdir(parents=True, exist_ok=True)
    if resume and out_path.exists():
        run = Run(**json.loads(out_path.read_text()))
    else:
        run = Run(run_id=run_id, label=label or run_id, model=cfg, taskset=manifest["name"],
                  taskset_version=f"gen{manifest.get('generator_version', 'user')}-seed{manifest.get('seed', 0)}",
                  judge_model=getattr(judge, "name", ""), git_sha=git_sha(),
                  started_at=datetime.now(UTC).isoformat(timespec="seconds"), repeats=repeats,
                  prompt_hashes={n: prompt_hash(n, taskset_dir) for n in sorted({t.prompt_template for t in tasks})})
    done = {(r.task_id, r.repeat) for r in run.results}
    todo = [(t, k) for t in tasks for k in range(repeats) if (t.id, k) not in done]
    adapter = build_adapter(cfg)

    def work(task: Task, k: int) -> TaskResult:
        prompt, ref = build_prompt(task, taskset_dir, native)
        ref.repeat = k
        out = call_with_retries(adapter, prompt, ref)
        out.raw = None if out.raw is None else out.raw
        grades, score, passed = grade_task(task, out, judge)
        return TaskResult(task_id=task.id, repeat=k, output=out, grades=grades, score=score, passed=passed)

    spent = run.total_cost_usd
    with ThreadPoolExecutor(max_workers=max(1, concurrency)) as pool:
        futs = {pool.submit(work, t, k): (t, k) for t, k in todo}
        try:
            for fut in as_completed(futs):
                res = fut.result()
                run.results.append(res)
                spent += res.output.cost_usd
                run.total_cost_usd = round(spent, 4)
                out_path.write_text(run.model_dump_json(indent=1))  # resumable after every task
                if progress:
                    progress(len(run.results), len(tasks) * repeats)
                if cost_cap is not None and spent > cost_cap:
                    for f in futs:
                        f.cancel()
                    raise CostCapExceeded(f"cost cap ${cost_cap:.2f} exceeded (spent ${spent:.2f}); run saved so far")
        finally:
            run.results.sort(key=lambda r: (r.task_id, r.repeat))
            run.finished_at = datetime.now(UTC).isoformat(timespec="seconds")
            out_path.write_text(run.model_dump_json(indent=1))
    return run
