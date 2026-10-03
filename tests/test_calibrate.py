from evalpond.calibrate import run_calibration
from evalpond.generator.taskset import build
from evalpond.graders.judge import MockJudge
from evalpond.runner import run_taskset
from evalpond.schema import ModelConfig


def test_calibration_labels_and_kappa(tmp_path):
    ts = tmp_path / "ts"
    build(42, ts)
    cfg = ModelConfig(name="m", adapter="mock", params={"skill": 0.5, "seed": 2})
    run = run_taskset(ts, cfg, run_id="r", out_dir=tmp_path, categories={"E"}, repeats=2, judge=MockJudge())
    answers = iter(["y", "n", "y", "y", "q"])
    res = run_calibration(run, ts, tmp_path / "labels.jsonl", n=10, ask=lambda _: next(answers), out=lambda _: None)
    assert res["n"] == 4 and 0 <= res["agree"] <= 4
    # labels persist, and a second session skips what is already labeled
    again = run_calibration(run, ts, tmp_path / "labels.jsonl", n=4, ask=lambda _: "q", out=lambda _: None)
    assert again["n"] == 4
