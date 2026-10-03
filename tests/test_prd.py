import json

from evalpond.generator.prd import build
from evalpond.grading import grade_task
from evalpond.runner import load_tasks
from evalpond.schema import ModelOutput


def _out(summary):
    return ModelOutput(text=json.dumps({"summary": summary}), parsed={"summary": summary})


def test_prd_set_shape_and_determinism(tmp_path):
    a = build(42, tmp_path / "a")
    build(42, tmp_path / "b")
    assert a["task_count"] == 40 and a["by_category"] == {"F": 20, "G": 10, "H": 10}
    assert (tmp_path / "a" / "tasks.jsonl").read_bytes() == (tmp_path / "b" / "tasks.jsonl").read_bytes()
    for p in (tmp_path / "a" / "docs").glob("*.md"):
        assert "synthetic" in p.read_text().lower()


def test_reference_summary_passes_and_every_bad_variant_fails(tmp_path):
    build(42, tmp_path / "ts")
    for t in load_tasks(tmp_path / "ts"):
        _, score, ok = grade_task(t, _out(t.expected["summary"]))
        assert ok, (t.id, score)
        for v in t.expected["mock_variants"]:
            _, score, ok = grade_task(t, _out(v))
            assert not ok, (t.id, v)


def test_invented_number_and_gap_acknowledgement(tmp_path):
    build(42, tmp_path / "ts")
    tasks = {t.id: t for t in load_tasks(tmp_path / "ts")}
    t = tasks["prd-gap-001"]
    guess = t.expected["summary"].replace("not stated in the document", "improve by 41 percent")
    assert not grade_task(t, _out(guess))[2]
    assert grade_task(t, _out("Goals are listed. The success metric is missing from the document."))[1] > 0
