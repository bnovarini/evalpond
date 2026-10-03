import json
import random

import pytest

from evalpond.generator import paystub as ps
from evalpond.generator.taskset import build, fixed, next_stub


@pytest.fixture(scope="module")
def taskset(tmp_path_factory):
    out = tmp_path_factory.mktemp("ts") / "income_v1"
    manifest = build(42, out)
    return out, manifest


def test_stub_math_is_consistent():
    for seed in range(40):
        s = ps.make_stub(random.Random(seed), overtime=True, bonus=seed % 2 == 0)
        total_out = sum(v for _, v in s.deductions) + sum(v for _, v in s.taxes)
        assert abs(s.gross - (s.regular_pay + s.overtime_pay + s.bonus)) < 0.011
        assert abs(s.net - (s.gross - total_out)) < 0.011
        assert s.period_start < s.period_end < s.pay_date or s.pay_date > s.period_end


def test_fixed_gross_ytd_is_period_times_gross():
    s = fixed(random.Random(3))
    assert abs(s.ytd_gross - s.gross * s.period_no) < 0.011
    n = next_stub(s)
    assert n.period_start > s.period_end and n.period_no == s.period_no + 1


def test_monthly_income_rule():
    s = ps.make_stub(random.Random(5), frequency="biweekly", bonus=True, overtime=True)
    assert abs(ps.monthly_income(s) - (s.base_gross + s.overtime_pay) * 26 / 12) < 0.01


def test_counts_and_split(taskset):
    _, m = taskset
    assert m["task_count"] == 60
    assert m["by_category"] == {"A": 20, "B": 12, "C": 10, "D": 8, "E": 10}
    assert 8 <= m["by_split"]["test"] <= 14
    assert m["not_present_tasks"] >= 6


def test_same_seed_is_byte_identical(taskset, tmp_path):
    out, _ = taskset
    build(42, tmp_path / "again")
    for f in sorted(out.rglob("*")):
        if f.is_file():
            assert f.read_bytes() == (tmp_path / "again" / f.relative_to(out)).read_bytes(), f


def test_every_document_is_watermarked(taskset):
    out, _ = taskset
    pdfs = list((out / "docs").glob("*.pdf"))
    assert pdfs
    for pdf in pdfs:
        assert b"evalpond-synthetic: true" in pdf.read_bytes(), pdf
        txt = pdf.with_suffix(".txt").read_text()
        assert "SYNTHETIC - NOT A REAL DOCUMENT" in txt
        truth = json.loads(pdf.with_suffix(".truth.json").read_text())
        assert truth["synthetic"] is True


def test_tasks_have_plain_language_fields(taskset):
    out, _ = taskset
    for line in (out / "tasks.jsonl").read_text().splitlines():
        t = json.loads(line)
        assert t["plain_title"] and t["why_it_matters"] and t["what_good_looks_like"]
        for f in ("plain_title", "why_it_matters"):
            assert "{" not in t[f] and "_" not in t[f]
