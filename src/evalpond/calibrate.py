"""Hand-label judged answers in the terminal, then measure how often the AI grader agrees with you."""
from __future__ import annotations

import json
import random
from collections.abc import Callable
from pathlib import Path

from .runner import load_tasks
from .schema import Run
from .stats import cohen_kappa


def judged_items(run: Run, taskset_dir: Path) -> list[dict]:
    tasks = {t.id: t for t in load_tasks(taskset_dir)}
    items = []
    for r in run.results:
        for g in r.grades:
            if g.method == "judge" and "answer" in g.details:
                spec = next(s for s in tasks[r.task_id].grading if s.method == "judge")
                items.append({"task_id": r.task_id, "repeat": r.repeat, "question": spec.judge_question,
                              "notes": spec.judge_notes, "answer": g.details["answer"],
                              "judge": int(g.score), "judge_reasoning": g.details.get("reasoning", "")})
    return items


def sample_balanced(items: list[dict], n: int, seed: int = 0) -> list[dict]:
    rng = random.Random(seed)
    pos = [i for i in items if i["judge"] == 1]
    neg = [i for i in items if i["judge"] == 0]
    rng.shuffle(pos), rng.shuffle(neg)
    take = []
    while len(take) < min(n, len(items)) and (pos or neg):
        for pool in (pos, neg):
            if pool and len(take) < n:
                take.append(pool.pop())
    rng.shuffle(take)
    return take


def load_labels(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def agreement(labels: list[dict]) -> dict:
    human = [int(x["human"]) for x in labels]
    judge = [int(x["judge"]) for x in labels]
    n = len(labels)
    agree = sum(h == j for h, j in zip(human, judge))
    return {"n": n, "agree": agree, "kappa": cohen_kappa(human, judge) if n else float("nan")}


def run_calibration(run: Run, taskset_dir: Path, labels_path: Path, n: int = 20,
                    ask: Callable[[str], str] = input, out: Callable[[str], None] = print) -> dict:
    existing = load_labels(labels_path)
    seen = {(x["task_id"], x["repeat"]) for x in existing}
    pool = [i for i in judged_items(run, taskset_dir) if (i["task_id"], i["repeat"]) not in seen]
    todo = sample_balanced(pool, max(0, n - len(existing)))
    labels_path.parent.mkdir(parents=True, exist_ok=True)
    out("You will see an answer and what it should say. Do NOT look for the AI grader's opinion; judge for yourself.")
    out("Type y if the answer is good, n if not, q to stop and save.\n")
    with labels_path.open("a") as f:
        for k, item in enumerate(todo, 1):
            out(f"--- {k}/{len(todo)}  ({item['task_id']}) ---")
            out(f"Assessing: {item['question']}")
            out(f"Reference: {item['notes']}")
            out(f"Answer:    {item['answer']}\n")
            while True:
                a = ask("Good answer? [y/n/q] ").strip().lower()
                if a in ("y", "n", "q"):
                    break
            if a == "q":
                break
            rec = {"task_id": item["task_id"], "repeat": item["repeat"], "human": int(a == "y"),
                   "judge": item["judge"], "answer": item["answer"]}
            f.write(json.dumps(rec) + "\n")
            f.flush()
    result = agreement(load_labels(labels_path))
    out(f"\nAI grader agrees with you on {result['agree']} of {result['n']} answers (kappa {result['kappa']:.2f}).")
    return result
