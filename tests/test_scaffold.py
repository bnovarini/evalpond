from evalpond.cli import build_parser
from evalpond.models.mock import MockAdapter
from evalpond.schema import DocumentRef, ModelConfig


def test_cli_has_commands():
    helptext = build_parser().format_help()
    for cmd in ["gen", "run", "report", "compare", "quickstart", "calibrate"]:
        assert cmd in helptext


def test_mock_is_deterministic():
    cfg = ModelConfig(name="m", adapter="mock", params={"skill": 0.5, "seed": 3})
    ref = DocumentRef(task_id="t1", oracle={"employer": "Harbor Lane Logistics", "gross_pay": 100.0})
    a = MockAdapter(cfg).run("p", ref)
    b = MockAdapter(cfg).run("p", ref)
    assert a.text == b.text


def test_quickstart_end_to_end(tmp_path, monkeypatch):
    from pathlib import Path

    from evalpond.cli import main
    root = Path(__file__).resolve().parents[1]
    monkeypatch.chdir(root)
    assert main(["quickstart", "--runs", str(tmp_path / "runs"), "--out", str(tmp_path / "site"), "--no-open"]) == 0
    assert (tmp_path / "site" / "index.html").exists()
    assert len(list((tmp_path / "runs").glob("*.json"))) == 3
