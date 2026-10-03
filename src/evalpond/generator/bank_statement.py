"""Synthetic bank statements with payroll deposits matching generated pay stubs, plus distractors."""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import date, timedelta

from . import names
from .paystub import StubData, r2
from .render import Block, Doc, Style

DATE_FMTS = ["%Y-%m-%d", "%m/%d", "%b %d", "%d-%b"]


@dataclass
class Txn:
    day: date
    desc: str
    amount: float  # + credit, - debit
    kind: str  # payroll | transfer_in | refund | p2p | card | bill


@dataclass
class StatementData:
    bank: str
    holder: str
    account: str
    period_start: date
    period_end: date
    opening: float
    closing: float
    txns: list[Txn] = field(default_factory=list)
    layout: int = 0
    defects: list[str] = field(default_factory=list)

    @property
    def income_deposits(self) -> list[Txn]:
        return [t for t in self.txns if t.kind == "payroll"]


def make_statement(rng: random.Random, holder: str, employer: str, stubs: list[StubData], *,
                   start: date, end: date, n_noise: int = 20) -> StatementData:
    """Payroll deposits come from `stubs` whose pay dates fall in [start, end]."""
    txns: list[Txn] = []
    for s in stubs:
        if start <= s.pay_date <= end:
            offset = rng.choice([0, 0, 1])
            day = min(end, s.pay_date + timedelta(days=offset))
            txns.append(Txn(day, f"ACH CREDIT {employer.upper()} PAYROLL", s.net, "payroll"))
    span = (end - start).days
    for _ in range(n_noise):
        day = start + timedelta(days=rng.randint(0, span))
        kind = rng.choices(["card", "bill", "transfer_in", "refund", "p2p"], [8, 3, 1, 1, 1])[0]
        if kind == "card":
            txns.append(Txn(day, f"POS {rng.choice(names.STORES)}", -r2(rng.uniform(4, 140)), kind))
        elif kind == "bill":
            txns.append(Txn(day, f"AUTOPAY {rng.choice(names.STORES)}", -r2(rng.uniform(40, 900)), kind))
        elif kind == "transfer_in":
            txns.append(Txn(day, f"TRANSFER FROM SAVINGS {names.masked_acct(rng)}", r2(rng.uniform(100, 1500)), kind))
        elif kind == "refund":
            txns.append(Txn(day, f"REFUND {rng.choice(names.STORES)}", r2(rng.uniform(8, 120)), kind))
        else:
            txns.append(Txn(day, f"P2P PAYMENT RECEIVED {names.person(rng).upper()}", r2(rng.uniform(15, 300)), kind))
    txns.sort(key=lambda t: (t.day, t.desc))
    opening = r2(rng.uniform(600, 4500))
    closing = r2(opening + sum(t.amount for t in txns))
    return StatementData(names.bank(rng), holder, names.masked_acct(rng), start, end, opening, closing, txns,
                         layout=rng.randrange(3))


BANK_STYLES = [
    ("%Y-%m-%d", "${:,.2f}", Style(table_style="lines", accent="#12467a")),
    ("%m/%d", "{:,.2f}", Style(table_style="zebra", accent="#7a4b12", font="Times")),
    ("%b %d", "${:,.2f}", Style(table_style="grid", accent="#2f5d3a", compact=True, size=8)),
]


def build_doc(s: StatementData) -> Doc:
    dfmt, mfmt, _ = BANK_STYLES[s.layout]
    m = lambda x: ("-" if x < 0 else "") + mfmt.format(abs(x))
    rows = [["Date", "Description", "Amount"]] + [[t.day.strftime(dfmt), t.desc, m(t.amount)] for t in s.txns]
    return Doc(
        title=f"{s.bank} - Account Statement",
        subtitle="Checking account",
        blocks=[
            Block("kv", "Account", [("Account holder", s.holder), ("Account number", s.account),
                                    ("Statement period", f"{s.period_start:%Y-%m-%d} to {s.period_end:%Y-%m-%d}"),
                                    ("Opening balance", m(s.opening)), ("Closing balance", m(s.closing))]),
            Block("table", "Transactions", rows),
        ],
    )


def style_of(s: StatementData) -> Style:
    return BANK_STYLES[s.layout][2]
