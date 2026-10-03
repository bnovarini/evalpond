"""Synthetic pay stubs. Math is computed, so ground truth is internally consistent by default."""
from __future__ import annotations

import calendar
import random
from dataclasses import dataclass, field
from datetime import date, timedelta

from . import names
from .render import Block, Doc, Style

PERIODS = {"weekly": 52, "biweekly": 26, "semi-monthly": 24, "monthly": 12}
MONTHLY_FACTOR = {"weekly": 52 / 12, "biweekly": 26 / 12, "semi-monthly": 2.0, "monthly": 1.0}


def r2(x: float) -> float:
    return round(x + 1e-9, 2)


@dataclass
class StubData:
    employer: str
    employer_address: str
    employee: str
    employee_id: str
    employee_address: str
    frequency: str
    hourly: bool
    rate: float  # hourly rate, or per-period base for salaried
    regular_hours: float
    overtime_hours: float
    bonus: float
    period_start: date
    period_end: date
    pay_date: date
    period_no: int
    regular_pay: float
    overtime_pay: float
    gross: float
    base_gross: float  # gross without overtime or bonus (what repeats each period)
    deductions: list[tuple[str, float]] = field(default_factory=list)  # pre-tax then post-tax
    taxes: list[tuple[str, float]] = field(default_factory=list)
    net: float = 0.0
    ytd_gross: float = 0.0
    ytd_net: float = 0.0
    ytd_lines: dict[str, float] = field(default_factory=dict)
    defects: list[str] = field(default_factory=list)  # injected defect codes (see inconsistencies.py)
    hide_ytd: bool = False
    hide_frequency: bool = False


def _period_dates(rng: random.Random, freq: str) -> tuple[date, date, int]:
    year = 2026
    if freq == "monthly":
        m = rng.randint(2, 11)
        s, e = date(year, m, 1), date(year, m, calendar.monthrange(year, m)[1])
        return s, e, m
    if freq == "semi-monthly":
        m = rng.randint(2, 11)
        if rng.random() < 0.5:
            return date(year, m, 1), date(year, m, 15), 2 * m - 1
        return date(year, m, 16), date(year, m, calendar.monthrange(year, m)[1]), 2 * m
    step = 7 if freq == "weekly" else 14
    start = date(year, 1, 5) + timedelta(days=step * rng.randint(4, 20))
    n = (start - date(year, 1, 5)).days // step + 1
    return start, start + timedelta(days=step - 1), n


def make_stub(rng: random.Random, *, frequency: str | None = None, employer: str | None = None,
              employee: str | None = None, overtime: bool = False, bonus: bool = False,
              fixed_gross: bool = False) -> StubData:
    freq = frequency or rng.choice(list(PERIODS))
    n = PERIODS[freq]
    hourly = rng.random() < 0.55
    start, end, k = _period_dates(rng, freq)
    ph = {"weekly": 40.0, "biweekly": 80.0, "semi-monthly": 86.67, "monthly": 173.33}[freq]
    if hourly:
        rate = r2(rng.uniform(15, 44))
        reg_pay = r2(rate * ph)
        ot_hours = float(rng.randint(2, 9)) if (overtime and not fixed_gross) else 0.0
        ot_pay = r2(rate * 1.5 * ot_hours)
    else:
        annual = rng.randint(32, 118) * 1000
        rate = r2(annual / n)
        ph, ot_hours, reg_pay, ot_pay = 0.0, 0.0, rate, 0.0
    bonus_amt = float(rng.choice([250, 400, 500, 750, 1000])) if (bonus and not fixed_gross) else 0.0
    gross = r2(reg_pay + ot_pay + bonus_amt)
    base = reg_pay

    def line_set(g: float) -> tuple[list[tuple[str, float]], list[tuple[str, float]]]:
        ded = [("Retirement plan (pre-tax)", r2(g * rate_ret)), ("Health plan (pre-tax)", health)]
        if post:
            ded.append(("Parking (post-tax)", post))
        taxable = g - ded[0][1] - ded[1][1]
        tax = [("Federal income tax", r2(taxable * 0.12)), ("State income tax", r2(taxable * state_rate)),
               ("Social security", r2(g * 0.062)), ("Medicare", r2(g * 0.0145))]
        return ded, tax

    rate_ret = rng.choice([0.03, 0.04, 0.05, 0.06])
    health = r2(rng.uniform(18, 95))
    post = r2(rng.choice([0, 0, 12, 25]))
    state_rate = rng.choice([0.03, 0.04, 0.045, 0.05])
    ded, tax = line_set(gross)
    net = r2(gross - sum(v for _, v in ded) - sum(v for _, v in tax))
    base_ded, base_tax = line_set(base)
    ytd_lines = {}
    for (lab, v), (_, bv) in zip(ded + tax, base_ded + base_tax):
        ytd_lines[lab] = r2(bv * (k - 1) + v)
    base_net = r2(base - sum(v for _, v in base_ded) - sum(v for _, v in base_tax))
    pay_date = end + timedelta(days=rng.choice([3, 5, 7]))
    while pay_date.weekday() >= 5:
        pay_date += timedelta(days=1)
    return StubData(
        employer=employer or names.employer(rng), employer_address=names.address(rng),
        employee=employee or names.person(rng), employee_id=names.masked_id(rng),
        employee_address=names.address(rng), frequency=freq, hourly=hourly, rate=rate,
        regular_hours=ph, overtime_hours=ot_hours, bonus=bonus_amt, period_start=start, period_end=end,
        pay_date=pay_date, period_no=k, regular_pay=reg_pay, overtime_pay=ot_pay, gross=gross,
        base_gross=base, deductions=ded, taxes=tax, net=net, ytd_gross=r2(base * (k - 1) + gross),
        ytd_net=r2(base_net * (k - 1) + net), ytd_lines=ytd_lines)


def monthly_income(stub: StubData) -> float:
    """Reference rule: recurring pay (base + overtime, no one-time bonus), annualized, / 12."""
    return r2((stub.base_gross + stub.overtime_pay) * PERIODS[stub.frequency] / 12)


# ---------- layouts ----------

DATE_FMTS = ["%Y-%m-%d", "%m/%d/%Y", "%b %d, %Y", "%d-%b-%y", "%B %d, %Y"]
MONEY_FMTS = ["${:,.2f}", "{:,.2f}", "USD {:,.2f}", "$ {:.2f}"]


@dataclass
class StubLayout:
    name: str
    style: Style
    date_fmt: str
    money_fmt: str
    words: dict
    tags: list[str]


def _L(name, date_i, money_i, words, tags, **style):
    return StubLayout(name, Style(**style), DATE_FMTS[date_i], MONEY_FMTS[money_i], words, tags)


W1 = dict(title="Earnings Statement", gross="Gross Pay", net="Net Pay", ded="Deductions", earn="Earnings",
          period="Pay Period", paydate="Pay Date", freq="Pay Frequency", ytd="YTD")
W2 = dict(title="Pay Advice", gross="Total Earnings", net="Take-Home Pay", ded="Withholdings", earn="Pay Details",
          period="Period Covered", paydate="Date Paid", freq="Schedule", ytd="Year to Date")
W3 = dict(title="Wage Statement", gross="Gross Wages", net="Net Amount Deposited", ded="Taxes and Deductions",
          earn="Wages", period="Work Period", paydate="Issued", freq="Frequency", ytd="Cumulative")
STUB_LAYOUTS = [
    _L("clean-single", 0, 0, W1, ["single-column"], kv_columns=1, table_style="grid", accent="#2b4c7e"),
    _L("two-column", 1, 1, W2, ["multi-column"], kv_columns=2, table_style="zebra", accent="#7a3b1e", font="Times"),
    _L("compact-lines", 2, 2, W3, ["compact", "odd-date-format"], kv_columns=2, table_style="lines", accent="#1f6b4f", compact=True, size=8),
    _L("grid-heavy", 3, 3, W1, ["table-heavy", "odd-date-format"], kv_columns=1, table_style="grid", accent="#444444", font="Courier", size=8),
    _L("zebra-wide", 4, 0, W2, ["long-date-format"], kv_columns=1, table_style="zebra", accent="#5b2a86", title_align=1),
    _L("lines-two", 1, 2, W3, ["multi-column", "currency-code"], kv_columns=2, table_style="lines", accent="#0d5c8a"),
]


def build_doc(s: StubData, lay: StubLayout) -> Doc:
    d = lambda x: x.strftime(lay.date_fmt)
    m = lambda x: lay.money_fmt.format(x)
    w = lay.words
    period_rows = [(w["period"], f"{d(s.period_start)} to {d(s.period_end)}"), (w["paydate"], d(s.pay_date)),
                   ("Pay period no.", f"{s.period_no}")]
    if not s.hide_frequency:
        period_rows.insert(2, (w["freq"], s.frequency.replace("-", " ").title()))
    ytd_on = not s.hide_ytd
    hdr = ["Description", "Hours", "Rate", "Current"] + ([w["ytd"]] if ytd_on else [])
    earn = [hdr]
    base_ytd = r2(s.base_gross * (s.period_no - 1))
    earn.append(["Regular pay", f"{s.regular_hours:.2f}" if s.hourly else "", m(s.rate), m(s.regular_pay)] + ([m(r2(base_ytd + s.regular_pay))] if ytd_on else []))
    if s.overtime_pay:
        earn.append(["Overtime (1.5x)", f"{s.overtime_hours:.2f}", m(r2(s.rate * 1.5)), m(s.overtime_pay)] + ([""] if ytd_on else []))
    if s.bonus:
        earn.append(["Bonus (one-time)", "", "", m(s.bonus)] + ([""] if ytd_on else []))
    earn.append([w["gross"], "", "", m(s.gross)] + ([m(s.ytd_gross)] if ytd_on else []))
    ded = [["Description", "Current"] + ([w["ytd"]] if ytd_on else [])]
    for lab, v in s.deductions + s.taxes:
        ded.append([lab, m(v)] + ([m(s.ytd_lines[lab])] if ytd_on else []))
    ded.append(["Net pay" if False else w["net"], m(s.net)] + ([m(s.ytd_net)] if ytd_on else []))
    return Doc(
        title=w["title"],
        subtitle=f"{s.employer}  |  {s.employer_address}",
        blocks=[
            Block("kv", "Employee", [("Name", s.employee), ("Employee ID", s.employee_id), ("Address", s.employee_address)]),
            Block("kv", "Period", period_rows),
            Block("table", w["earn"], earn),
            Block("table", w["ded"], ded),
            Block("kv", "", [(w["net"], m(s.net))]),
        ],
    )
