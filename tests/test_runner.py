import json

import pytest

from evalpond.generator.taskset import build
from evalpond.runner import CostCapExceeded, parse_json, run_taskset
from evalpond.schema import ModelConfig


@pytest.fixture(scope="module")
def ts(tmp_path_factory):
    out = tmp_path_factory.mktemp("rt") / "income_v1"
    build(42, out)
    return out


def test_parse_json_variants():
    assert parse_json('{"a": 1}') == {"a": 1}
    assert parse_json('```json\n{"a": 1}\n```') == {"a": 1}
    assert parse_json('Sure! {"a": 1} hope that helps') == {"a": 1}
    assert parse_json("no json here") is None


def test_run_is_reproducible_and_resumable(ts, tmp_path):
    cfg = ModelConfig(name="m", adapter="mock", params={"skill": 0.8, "seed": 1})
    r1 = run_taskset(ts, cfg, run_id="a", out_dir=tmp_path, categories={"A", "B"})
    r2 = run_taskset(ts, cfg, run_id="b", out_dir=tmp_path, categories={"A", "B"})
    assert [x.score for x in r1.results] == [x.score for x in r2.results]
    # resume: nothing left to do, same results
    r3 = run_taskset(ts, cfg, run_id="a", out_dir=tmp_path, categories={"A", "B"})
    assert len(r3.results) == len(r1.results) == 32
    saved = json.loads((tmp_path / "a.json").read_text())
    assert saved["model"]["name"] == "m" and saved["prompt_hashes"] and saved["taskset_version"]


def test_skill_orders_models(ts, tmp_path):
    strong = ModelConfig(name="s", adapter="mock", params={"skill": 0.95, "seed": 1})
    weak = ModelConfig(name="w", adapter="mock", params={"skill": 0.3, "seed": 1})
    a = run_taskset(ts, strong, run_id="s", out_dir=tmp_path, categories={"A", "B"})
    b = run_taskset(ts, weak, run_id="w", out_dir=tmp_path, categories={"A", "B"})
    assert sum(r.passed for r in a.results) > sum(r.passed for r in b.results)


def test_cost_cap_aborts(ts, tmp_path):
    cfg = ModelConfig(name="c", adapter="mock", params={"skill": 1, "cost_per_call": 1.0})
    with pytest.raises(CostCapExceeded):
        run_taskset(ts, cfg, run_id="cap", out_dir=tmp_path, categories={"A"}, cost_cap=2.5, concurrency=1)
    assert (tmp_path / "cap.json").exists()


def test_all_categories_with_mock_judge(ts, tmp_path):
    from evalpond.graders.judge import MockJudge
    cfg = ModelConfig(name="m", adapter="mock", params={"skill": 1.0, "seed": 1})
    run = run_taskset(ts, cfg, run_id="all", out_dir=tmp_path, judge=MockJudge())
    assert len(run.results) == 60
    assert all(r.passed for r in run.results), [r.task_id for r in run.results if not r.passed]
    d = next(r for r in run.results if r.task_id.startswith("pack-"))
    assert {g.method for g in d.grades} == {"rubric"}
    e = next(r for r in run.results if r.task_id.startswith("check-"))
    assert {g.method for g in e.grades} == {"exact", "judge"}


def test_missing_judge_is_a_clear_error(ts, tmp_path):
    cfg = ModelConfig(name="m", adapter="mock", params={"skill": 1.0})
    with pytest.raises(RuntimeError, match="--judge"):
        run_taskset(ts, cfg, run_id="nj", out_dir=tmp_path, categories={"E"})
