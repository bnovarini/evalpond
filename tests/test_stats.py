import math

from evalpond import stats
from evalpond.schema import GradeResult, ModelConfig, ModelOutput, Run, TaskResult


def test_wilson_known_values():
    lo, hi = stats.wilson(8, 10)
    assert abs(lo - 0.4902) < 0.002 and abs(hi - 0.9433) < 0.002
    assert stats.wilson(0, 10)[0] == 0 and stats.wilson(10, 10)[1] == 1
    assert stats.wilson(0, 0) == (0.0, 1.0)


def test_wilson_width_at_n60_is_about_ten_points():
    lo, hi = stats.wilson(48, 60)  # 80%
    assert 0.08 < (hi - lo) / 2 < 0.11


def test_mcnemar_known_cases():
    assert stats.mcnemar_exact(0, 0) == 1.0
    assert abs(stats.mcnemar_exact(5, 0) - 0.0625) < 1e-9
    assert stats.mcnemar_exact(3, 3) == 1.0
    assert abs(stats.mcnemar_exact(1, 9) - 0.021484375) < 1e-9


def test_kappa():
    assert stats.cohen_kappa([1, 0, 1, 0], [1, 0, 1, 0]) == 1.0
    assert abs(stats.cohen_kappa([1, 1, 0, 0], [1, 0, 1, 0])) < 1e-9  # chance-level agreement
    assert stats.cohen_kappa([1, 1, 1, 1], [1, 1, 1, 1]) == 1.0
    assert math.isnan(stats.cohen_kappa([], []))


def test_pearson():
    assert abs(stats.pearson([1, 2, 3, 4], [2, 4, 6, 8]) - 1) < 1e-9
    assert math.isnan(stats.pearson([1, 1, 1], [1, 2, 3]))


def _run(name, passes):
    cfg = ModelConfig(name=name, adapter="mock")
    rs = [TaskResult(task_id=f"t{i}", output=ModelOutput(), grades=[GradeResult(method="exact", score=float(p))],
                     score=float(p), passed=bool(p)) for i, p in enumerate(passes)]
    return Run(run_id=name, model=cfg, taskset="x", results=rs)


def test_compare_counts_flips_and_verdict():
    a = _run("a", [1] * 10 + [0] * 10)
    b = _run("b", [1] * 10 + [1] * 8 + [0] * 2)  # 8 fixed, none regressed
    c = stats.compare_runs(a, b)
    assert len(c.fixed) == 8 and not c.regressed and c.p_value < 0.05 and c.verdict == "likely better"
    c2 = stats.compare_runs(b, a)
    assert c2.verdict == "likely worse" and len(c2.regressed) == 8


def test_small_change_is_not_significant():
    a = _run("a", [1] * 12 + [0] * 8)
    b = _run("b", [1] * 11 + [0] + [1, 1] + [0] * 6)  # one regression, two fixes
    c = stats.compare_runs(a, b)
    assert len(c.fixed) == 2 and len(c.regressed) == 1
    assert c.verdict == "no clear difference"


def test_flaky():
    cfg = ModelConfig(name="f", adapter="mock")
    mk = lambda k, p: TaskResult(task_id="t", repeat=k, output=ModelOutput(), score=float(p), passed=bool(p))
    run = Run(run_id="f", model=cfg, taskset="x", results=[mk(0, 1), mk(1, 0), mk(2, 1)])
    assert stats.flaky_tasks(run) == ["t"]
