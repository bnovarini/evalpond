import json
import re
from importlib import resources

import pytest

from evalpond.generator.taskset import build
from evalpond.graders.judge import MockJudge
from evalpond.report import copy as C
from evalpond.report.build import build_data, build_report
from evalpond.runner import run_taskset
from evalpond.schema import ModelConfig


@pytest.fixture(scope="module")
def setup(tmp_path_factory):
    root = tmp_path_factory.mktemp("rep")
    ts = root / "ts"
    build(42, ts)
    for name, skill in [("weak", 0.4), ("strong", 0.9)]:
        run_taskset(ts, ModelConfig(name=name, adapter="mock", params={"skill": skill, "seed": 1}),
                    run_id=name, out_dir=root / "runs", judge=MockJudge())
    return root, ts


def test_report_builds_and_embeds_data(setup, tmp_path):
    root, ts = setup
    path = build_report(root / "runs", ts, tmp_path / "site", None, "t")
    html = path.read_text()
    assert "ALL DOCUMENTS IN THIS REPORT ARE SYNTHETIC" in html
    data = json.loads(re.search(r'<script id="data" type="application/json">(.*?)</script>', html, re.DOTALL).group(1).replace("<\\/", "</"))
    assert len(data["runs"]) == 2 and len(data["tasks"]) == 60
    assert "weak|strong" in data["compare"] and "strong|weak" in data["compare"]
    assert data["compare"]["weak|strong"]["verdict"] == "likely better"
    assert data["compare"]["strong|weak"]["verdict"] == "likely worse"


def test_every_task_card_has_plain_text(setup):
    root, ts = setup
    data = build_data(root / "runs", ts)
    assert all(t["title"] and t["why"] and t["good"] and t["docs"] for t in data["tasks"])


def test_plain_copy_has_no_jargon(setup):
    root, ts = setup
    texts = list(C.PLAIN.values())
    data = build_data(root / "runs", ts)
    for c in data["compare"].values():
        texts += [c["sentence"], c["advice"], *c["notes"]]
    for t in texts:
        for bad in C.BANNED_IN_PLAIN:
            assert bad not in t.lower(), f"jargon '{bad}' in: {t}"
    # jargon may only live in DETAILS copy, which the UI shows inside a "Details for the curious" fold
    pkg = resources.files("evalpond.report")
    for name in ("app.js", "template.html"):
        src = pkg.joinpath(name).read_text().lower()
        for bad in C.BANNED_IN_PLAIN:
            assert bad not in src, f"jargon '{bad}' hard-coded in {name}"


def test_details_copy_is_wrapped_in_folds():
    js = resources.files("evalpond.report").joinpath("app.js").read_text()
    assert "Details for the curious" in js
    assert "DT.luck" in js and js.count("DT.") >= 3
