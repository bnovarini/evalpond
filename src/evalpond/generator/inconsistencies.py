"""Labeled defect injector for category E.

These simulate INTERNAL INCONSISTENCIES so we can test whether a model notices them. This is
for evaluation only. Nothing here is meant to make a document look authentic.
"""
from __future__ import annotations

import random
from datetime import timedelta

from .bank_statement import StatementData
from .paystub import StubData, r2

DEFECTS = {
    "ytd_mismatch": "Year-to-date gross does not match the pay period number times the current gross pay.",
    "net_math": "Net pay does not equal gross pay minus the listed deductions and taxes.",
    "dates_out_of_order": "The dates are out of order (period start after period end, or pay date before the period ends).",
    "deposit_mismatch": "The bank deposit amount does not match the net pay on the stub.",
    "employer_mismatch": "The employer named on the bank deposit differs from the employer on the stub.",
}
STUB_ONLY = ["ytd_mismatch", "net_math", "dates_out_of_order"]
NEEDS_STATEMENT = ["deposit_mismatch", "employer_mismatch"]


def inject_stub(s: StubData, code: str, rng: random.Random) -> None:
    if code == "ytd_mismatch":
        s.ytd_gross = r2(s.ytd_gross + rng.choice([-1, 1]) * rng.choice([850.0, 1200.0, 2300.0]))
    elif code == "net_math":
        s.net = r2(s.net + rng.choice([-1, 1]) * rng.choice([60.0, 135.5, 240.0]))
    elif code == "dates_out_of_order":
        if rng.random() < 0.5:
            s.period_start, s.period_end = s.period_end, s.period_start
        else:
            s.pay_date = s.period_end - timedelta(days=rng.choice([3, 6]))
    else:
        raise ValueError(code)
    s.defects.append(code)


def inject_statement(st: StatementData, stub: StubData, code: str, rng: random.Random) -> None:
    dep = next(t for t in st.txns if t.kind == "payroll")
    if code == "deposit_mismatch":
        delta = rng.choice([-1, 1]) * rng.choice([75.0, 210.0, 480.0])
        dep.amount = r2(dep.amount + delta)
        st.closing = r2(st.closing + delta)
    elif code == "employer_mismatch":
        from . import names
        other = names.employer(rng)
        while other == stub.employer:
            other = names.employer(rng)
        dep.desc = f"ACH CREDIT {other.upper()} PAYROLL"
    else:
        raise ValueError(code)
    st.defects.append(code)
