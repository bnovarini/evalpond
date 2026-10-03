import json

import pytest

from evalpond.cli import main
from evalpond.explain import explain_run
from evalpond.runner import load_tasks
from evalpond.schema import Run
from evalpond.taskkit import add_task, validate_taskset


def _add(ts, **kw):
    spec = {"failure_mode": "Invents a refund window", "question": "How many days?",
            "expected": {"refund_days": 30},
            "grading": [{"method": "exact", "fields": ["refund_days"]}], **kw.pop("spec", {})}
    return add_task(ts, spec, kw.pop("inputs", ["Returns accepted within 30 days."]))


def test_add_and_validate_roundtrip(tmp_path):
    ts = tmp_path / "ts"
    r = _add(ts)
    assert r["ok"] and r["written"] and r["id"] == "invents-a-refund-window-01"
    assert [t.id for t in load_tasks(ts)] == [r["id"]]
    rep = validate_taskset(ts)
    assert rep["ok"] and rep["summary"]["self_tested"] == 1


def test_refuses_bad_exact_field_and_leaves_no_files(tmp_path):
    ts = tmp_path / "ts"
    r = _add(ts, spec={"grading": [{"method": "exact", "fields": ["nope"]}]})
    assert not r["ok"] and r["errors"][0]["code"] == "exact_field_unknown"
    assert not list((ts / "docs").glob("*")) if (ts / "docs").exists() else True


@pytest.mark.parametrize("text", ["write to bob@gmail.com", "SSN 123-45-6789", "call 415-867-5309", "acct 123456789012345"])
def test_refuses_personal_data(tmp_path, text):
    r = _add(tmp_path / "ts", inputs=[text])
    assert not r["ok"] and any(e["code"] == "pii" for e in r["errors"])


def test_example_addresses_are_fine(tmp_path):
    assert _add(tmp_path / "ts", inputs=["Contact help@example.com, 30 days. Call 555-0100."])["ok"]


def test_gold_must_pass_and_wrong_must_fail(tmp_path):
    ts = tmp_path / "ts"
    ok = add_task(ts, {"failure_mode": "Tone", "question": "Reply.", "expected": {"note": "x"},
                       "grading": [{"method": "rubric", "rubric": [
                           {"id": "a", "text": "mentions sorry", "check": "mentions:sorry"},
                           {"id": "b", "text": "no blame", "check": "none_of:your fault"}]}]}, ["Late order."])
    assert ok["ok"]
    bad = add_task(ts, {"failure_mode": "Tone", "question": "Reply.", "expected": {"note": "x"},
                        "grading": [{"method": "rubric", "rubric": [
                            {"id": "a", "text": "contradiction", "check": "mentions:sorry"},
                            {"id": "b", "text": "contradiction", "check": "none_of:sorry"}]}]}, ["Late order."])
    assert not bad["ok"] and bad["errors"][0]["code"] == "gold_fails"
    vacuous = add_task(ts, {"failure_mode": "Tone", "question": "Reply.", "expected": {"note": "x"},
                            "grading": [{"method": "rubric", "rubric": [{"id": "a", "text": "short", "check": "max_words:50"}]}]}, ["Late."])
    assert vacuous["ok"] and any(w["code"] == "cannot_fail" for w in vacuous["warnings"])


def test_key_not_in_document_warns(tmp_path):
    r = _add(tmp_path / "ts", spec={"expected": {"refund_days": 45}}, inputs=["Returns accepted within 30 days."])
    assert r["ok"] and any(w["code"] == "key_not_in_document" for w in r["warnings"])


def test_duplicate_id_and_missing_prompt(tmp_path):
    ts = tmp_path / "ts"
    assert _add(ts, spec={"id": "t1"})["ok"]
    assert not _add(ts, spec={"id": "t1"})["ok"]
    assert not _add(ts, spec={"id": "t2", "prompt_template": "nope_v9"})["ok"]


def test_cli_end_to_end_with_mock_and_explain(tmp_path, capsys):
    ts, runs = tmp_path / "ts", tmp_path / "runs"
    for i in range(3):
        assert main(["add-task", "--taskset", str(ts), "--failure-mode", "Invents a refund window", "--question", "Days?",
                     "--input", f"Returns accepted within {20 + i} days.", "--expected", json.dumps({"refund_days": 20 + i}),
                     "--exact", "refund_days"]) == 0
    assert main(["validate", str(ts)]) == 0
    assert main(["run", "--model", "mock-weak", "--taskset", str(ts), "--out", str(runs), "--run-id", "r"]) == 0
    capsys.readouterr()
    assert main(["explain", str(runs / "r.json"), "--taskset", str(ts), "--json"]) == 0
    e = json.loads(capsys.readouterr().out)
    assert e["answers"] == 3 and e["by_category"][0]["category"] == "invents-a-refund-window"


def test_explain_labels_made_up_answers(tmp_path):
    ts = tmp_path / "ts"
    add_task(ts, {"failure_mode": "Invents", "question": "Days?", "expected": {"d": None},
                  "grading": [{"method": "exact", "fields": ["d"]}]}, ["Gift cards are final sale."])
    from evalpond.graders.rubric import grade_rubric  # noqa: F401
    from evalpond.grading import grade_task
    from evalpond.schema import ModelConfig, ModelOutput, TaskResult
    t = load_tasks(ts)[0]
    out = ModelOutput(text="{}", parsed={"d": 30})
    g, s, p = grade_task(t, out)
    run = Run(run_id="x", model=ModelConfig(name="m", adapter="mock"), taskset="ts",
              results=[TaskResult(task_id=t.id, output=out, grades=g, score=s, passed=p)])
    e = explain_run(run, ts)
    assert e["patterns"][0]["kind"] == "made_something_up" and e["failures"][0]["failure_mode"] == "invents"


def test_real_model_needs_prices_and_gets_default_cap(tmp_path, capsys):
    ts = tmp_path / "ts"
    _add(ts)
    m = tmp_path / "m.yaml"
    m.write_text("models:\n  - name: x\n    adapter: anthropic\n    model: m\n    api_key_env: NOPE_KEY\n")
    assert main(["run", "--model", "x", "--models", str(m), "--taskset", str(ts), "--out", str(tmp_path / "r")]) == 2
    assert "price_in" in capsys.readouterr().err
