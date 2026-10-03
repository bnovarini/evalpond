from evalpond.graders import normalize as N
from evalpond.graders.exact import grade_exact
from evalpond.schema import GradeSpec


def test_money_normalizer():
    assert N.money("$1,234.50") == 1234.5
    assert N.money("USD 1,234.50") == 1234.5
    assert N.money("(12.00)") == -12.0
    assert N.money("abc") is None
    assert N.money(True) is None


def test_date_normalizer():
    assert N.date_iso("03/30/2026") == "2026-03-30"
    assert N.date_iso("Mar 30, 2026") == "2026-03-30"
    assert N.date_iso("30-Mar-26") == "2026-03-30"
    assert N.date_iso("not a date") is None


def test_name_and_frequency():
    assert N.name("Harbor Lane, Logistics!") == "harbor lane logistics"
    assert N.frequency("Bi-Weekly") == "biweekly"
    assert N.frequency("Semi Monthly") == "semi-monthly"


def test_abstain_is_rewarded_and_inventing_is_punished():
    spec = GradeSpec(method="exact", fields=["ytd_gross"])
    assert grade_exact(spec, {"ytd_gross": None}, {"ytd_gross": None}).score == 1
    assert grade_exact(spec, {"ytd_gross": None}, {"ytd_gross": "N/A"}).score == 1
    assert grade_exact(spec, {"ytd_gross": None}, {"ytd_gross": 5000}).score == 0
    assert grade_exact(spec, {"ytd_gross": 5000.0}, {"ytd_gross": None}).score == 0


def test_money_tolerance_and_partial_credit():
    spec = GradeSpec(method="exact", fields=["gross_pay", "employer"], tolerance=0.005)
    exp = {"gross_pay": 100.0, "employer": "Harbor Lane Logistics"}
    r = grade_exact(spec, exp, {"gross_pay": "$100.00", "employer": "harbor lane logistics."})
    assert r.score == 1
    r = grade_exact(spec, exp, {"gross_pay": 100.5, "employer": "Harbor Lane Logistics"})
    assert r.score == 0.5 and r.details["all_correct"] is False


def test_deposit_lists_and_sets():
    spec = GradeSpec(method="exact", fields=["income_deposits", "issues"])
    exp = {"income_deposits": [{"date": "2026-05-29", "amount": 831.62}], "issues": []}
    ok = {"income_deposits": [{"date": "05/29/2026", "amount": "$831.62"}], "issues": []}
    assert grade_exact(spec, exp, ok).score == 1
    bad = {"income_deposits": [{"date": "2026-05-29", "amount": 800}], "issues": ["x"]}
    assert grade_exact(spec, exp, bad).score == 0
    assert grade_exact(spec, exp, {"income_deposits": [], "issues": []}).score == 0.5


def test_bool_and_frequency_fields():
    spec = GradeSpec(method="exact", fields=["complete", "pay_frequency"])
    exp = {"complete": False, "pay_frequency": "biweekly"}
    assert grade_exact(spec, exp, {"complete": "false", "pay_frequency": "Bi-weekly"}).score == 1
    assert grade_exact(spec, exp, {"complete": True, "pay_frequency": "weekly"}).score == 0
