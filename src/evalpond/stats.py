"""Statistics for eval results: intervals, paired comparison, agreement. Standard library only."""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field

from .schema import Run, TaskResult


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson score interval for a pass rate. Better than the normal approximation near 0 or 1."""
    if n == 0:
        return 0.0, 1.0
    p = k / n
    d = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / d
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return max(0.0, centre - half), min(1.0, centre + half)


def mcnemar_exact(b: int, c: int) -> float:
    """Two-sided exact McNemar p-value. b = pass->fail flips, c = fail->pass flips. Only flips carry information."""
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    tail = sum(math.comb(n, i) for i in range(k + 1)) / 2**n
    return min(1.0, 2 * tail)


def paired_bootstrap(diffs: list[float], iters: int = 4000, seed: int = 0) -> tuple[float, float]:
    """95% bootstrap interval for the mean of per-task score differences (B minus A)."""
    if not diffs:
        return 0.0, 0.0
    rng = random.Random(seed)
    n = len(diffs)
    means = sorted(sum(diffs[rng.randrange(n)] for _ in range(n)) / n for _ in range(iters))
    return means[int(0.025 * iters)], means[int(0.975 * iters) - 1]


def cohen_kappa(a: list[int], b: list[int]) -> float:
    """Agreement between two binary raters, corrected for chance. 1 = perfect, 0 = no better than chance."""
    n = len(a)
    if n == 0 or n != len(b):
        return float("nan")
    po = sum(x == y for x, y in zip(a, b)) / n
    pa, pb = sum(a) / n, sum(b) / n
    pe = pa * pb + (1 - pa) * (1 - pb)
    if pe == 1:
        return 1.0 if po == 1 else 0.0
    return (po - pe) / (1 - pe)


def pearson(x: list[float], y: list[float]) -> float:
    n = len(x)
    if n < 3:
        return float("nan")
    mx, my = sum(x) / n, sum(y) / n
    sx = math.sqrt(sum((v - mx) ** 2 for v in x))
    sy = math.sqrt(sum((v - my) ** 2 for v in y))
    if sx == 0 or sy == 0:
        return float("nan")
    return sum((a - mx) * (b - my) for a, b in zip(x, y)) / (sx * sy)


def min_detectable_gap(n: int, p: float = 0.8, z: float = 1.96) -> float:
    """Rough size of a pass-rate gap that two independent runs of n tasks can tell apart from luck."""
    return z * math.sqrt(2 * p * (1 - p) / max(n, 1))


# ---------- run-level helpers ----------

def task_passes(run: Run) -> dict[str, float]:
    """Pass rate per task across repeats (1.0 or 0.0 with a single repeat)."""
    by: dict[str, list[bool]] = {}
    for r in run.results:
        by.setdefault(r.task_id, []).append(r.passed)
    return {t: sum(v) / len(v) for t, v in by.items()}


def task_scores(run: Run) -> dict[str, float]:
    by: dict[str, list[float]] = {}
    for r in run.results:
        by.setdefault(r.task_id, []).append(r.score)
    return {t: sum(v) / len(v) for t, v in by.items()}


def flaky_tasks(run: Run) -> list[str]:
    """Tasks that passed in some repeats and failed in others."""
    return sorted(t for t, p in task_passes(run).items() if 0 < p < 1)


@dataclass
class Comparison:
    n: int
    fixed: list[str] = field(default_factory=list)
    regressed: list[str] = field(default_factory=list)
    unchanged_pass: int = 0
    unchanged_fail: int = 0
    p_value: float = 1.0
    mean_diff: float = 0.0
    diff_ci: tuple[float, float] = (0.0, 0.0)
    pass_a: float = 0.0
    pass_b: float = 0.0
    verdict: str = "no clear difference"
    min_gap: float = 0.0
    notes: list[str] = field(default_factory=list)


def compare_runs(a: Run, b: Run, alpha: float = 0.05) -> Comparison:
    pa, pb = task_passes(a), task_passes(b)
    ids = sorted(set(pa) & set(pb))
    c = Comparison(n=len(ids))
    sa, sb = task_scores(a), task_scores(b)
    for t in ids:
        x, y = pa[t] >= 0.5, pb[t] >= 0.5
        if x and not y:
            c.regressed.append(t)
        elif y and not x:
            c.fixed.append(t)
        elif x:
            c.unchanged_pass += 1
        else:
            c.unchanged_fail += 1
    c.p_value = mcnemar_exact(len(c.regressed), len(c.fixed))
    diffs = [sb[t] - sa[t] for t in ids]
    c.mean_diff = sum(diffs) / len(diffs) if diffs else 0.0
    c.diff_ci = paired_bootstrap(diffs)
    c.pass_a = sum(pa[t] >= 0.5 for t in ids) / max(len(ids), 1)
    c.pass_b = sum(pb[t] >= 0.5 for t in ids) / max(len(ids), 1)
    c.min_gap = min_detectable_gap(len(ids))
    if c.p_value < alpha and len(c.fixed) != len(c.regressed):
        c.verdict = "likely better" if len(c.fixed) > len(c.regressed) else "likely worse"
    if abs(c.pass_b - c.pass_a) < c.min_gap and c.verdict == "no clear difference":
        c.notes.append(f"With {c.n} tasks, only gaps bigger than about {c.min_gap * 100:.0f} points can be told apart from luck.")
    return c


def results_by(run: Run, key) -> dict[str, list[TaskResult]]:
    out: dict[str, list[TaskResult]] = {}
    for r in run.results:
        out.setdefault(key(r), []).append(r)
    return out
