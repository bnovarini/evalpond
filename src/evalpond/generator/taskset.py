"""Builds the income_v1 task set from a seed. Same seed gives a byte-identical set."""
from __future__ import annotations

import calendar
import dataclasses
import json
import random
import shutil
from datetime import date, timedelta
from pathlib import Path

import yaml

from ..schema import GradeSpec, RubricItem, Task
from . import bank_statement as bs
from . import inconsistencies as inc
from . import paystub as ps
from .render import to_pdf, to_text

FRIENDLY = {"clean-single": "clean single-column", "two-column": "two-column", "compact-lines": "compact",
            "grid-heavy": "table-heavy", "zebra-wide": "wide-format", "lines-two": "lined two-column"}
GENERATOR_VERSION = "1"
TASKSET = "income_v1"


def _iso(d: date) -> str:
    return d.isoformat()


def _sub_rng(seed: int, key: str) -> random.Random:
    return random.Random(f"{seed}:{key}")


def next_stub(s: ps.StubData) -> ps.StubData:
    """The following pay period for a fixed-gross stub (same amounts, shifted dates)."""
    if s.frequency in ("weekly", "biweekly"):
        step = timedelta(days=7 if s.frequency == "weekly" else 14)
        start, end, pay = s.period_start + step, s.period_end + step, s.pay_date + step
    elif s.frequency == "monthly":
        y, m = (s.period_start.year, s.period_start.month + 1)
        start = date(y, m, 1)
        end = date(y, m, calendar.monthrange(y, m)[1])
        pay = end + (s.pay_date - s.period_end)
    else:  # semi-monthly
        if s.period_start.day == 1:
            start, end = s.period_start.replace(day=16), s.period_start.replace(day=calendar.monthrange(s.period_start.year, s.period_start.month)[1])
        else:
            y, m = s.period_start.year, s.period_start.month + 1
            start, end = date(y, m, 1), date(y, m, 15)
        pay = end + (s.pay_date - s.period_end)
    k = s.period_no + 1
    ytd_lines = {lab: ps.r2(v / s.period_no * k) for lab, v in s.ytd_lines.items()}
    return dataclasses.replace(s, period_start=start, period_end=end, pay_date=pay, period_no=k,
                               ytd_gross=ps.r2(s.gross * k), ytd_net=ps.r2(s.net * k), ytd_lines=ytd_lines,
                               defects=[])


def fixed(rng: random.Random, **kw) -> ps.StubData:
    s = ps.make_stub(rng, fixed_gross=True, **kw)
    s.ytd_gross = ps.r2(s.gross * s.period_no)
    s.ytd_net = ps.r2(s.net * s.period_no)
    s.ytd_lines = {lab: ps.r2(v * s.period_no) for lab, v in [*s.deductions, *s.taxes]}
    return s


class Builder:
    def __init__(self, seed: int, out: Path):
        self.seed, self.out, self.docs_dir = seed, out, out / "docs"
        self.tasks: list[Task] = []

    # -- document writing
    def write_stub(self, tid: str, i: int, s: ps.StubData, lay: ps.StubLayout) -> tuple[str, str]:
        doc = ps.build_doc(s, lay)
        stem = f"{tid}-{i}"
        to_pdf(doc, lay.style, self.docs_dir / f"{stem}.pdf")
        (self.docs_dir / f"{stem}.txt").write_text(to_text(doc))
        truth = {"type": "pay_stub", "synthetic": True, "layout": lay.name, "defects": s.defects,
                 "data": json.loads(json.dumps(dataclasses.asdict(s), default=str))}
        (self.docs_dir / f"{stem}.truth.json").write_text(json.dumps(truth, indent=1, sort_keys=True))
        return f"docs/{stem}.pdf", f"docs/{stem}.txt"

    def write_statement(self, tid: str, i: int, st: bs.StatementData) -> tuple[str, str]:
        doc = bs.build_doc(st)
        stem = f"{tid}-{i}"
        to_pdf(doc, bs.style_of(st), self.docs_dir / f"{stem}.pdf")
        (self.docs_dir / f"{stem}.txt").write_text(to_text(doc))
        truth = {"type": "bank_statement", "synthetic": True, "defects": st.defects,
                 "data": json.loads(json.dumps(dataclasses.asdict(st), default=str))}
        (self.docs_dir / f"{stem}.truth.json").write_text(json.dumps(truth, indent=1, sort_keys=True))
        return f"docs/{stem}.pdf", f"docs/{stem}.txt"

    def add(self, **kw) -> None:
        self.tasks.append(Task(**kw))

    # -- categories
    def cat_a(self, n: int = 20) -> None:
        diffs = ["easy"] * 6 + ["medium"] * 9 + ["hard"] * 5
        negatives = {3: "hide_frequency", 7: "hide_ytd", 12: "hide_ytd", 15: "hide_frequency", 17: "hide_frequency"}
        for i in range(n):
            tid, d = f"stub-{i + 1:03d}", diffs[i]
            rng = _sub_rng(self.seed, tid)
            hard = d == "hard"
            s = ps.make_stub(rng, overtime=hard or (d == "medium" and rng.random() < .4), bonus=hard and rng.random() < .8)
            neg = negatives.get(i)
            s.hide_ytd, s.hide_frequency = neg == "hide_ytd", neg == "hide_frequency"
            lay = ps.STUB_LAYOUTS[0] if d == "easy" else rng.choice(ps.STUB_LAYOUTS[1:])
            pdf, txt = self.write_stub(tid, 1, s, lay)
            expected = {"employer": s.employer, "employee": s.employee, "gross_pay": s.gross, "net_pay": s.net,
                        "period_start": _iso(s.period_start), "period_end": _iso(s.period_end),
                        "pay_frequency": None if s.hide_frequency else s.frequency,
                        "ytd_gross": None if s.hide_ytd else s.ytd_gross}
            tags = list(lay.tags) + (["distractor-gross"] if (s.bonus or s.overtime_pay) else [])
            tags += ["not-present"] if neg else []
            self.add(id=tid, category="A", difficulty=d, documents=[pdf], text_documents=[txt],
                     prompt_template="extract_stub_v1", expected=expected,
                     grading=[GradeSpec(method="exact", fields=list(expected))], tags=tags,
                     plain_title=f"Read the key fields from a {FRIENDLY[lay.name]} pay stub"
                     + (" that is missing some information" if neg else ""),
                     why_it_matters="Underwriting starts with getting the basic facts right: who, how much, which period.",
                     what_good_looks_like="Every field matches the document. A field the document does not show is reported as missing, not guessed.")

    def cat_b(self, n: int = 12) -> None:
        diffs = ["easy"] * 3 + ["medium"] * 6 + ["hard"] * 3
        for i in range(n):
            tid, d = f"bank-{i + 1:03d}", diffs[i]
            rng = _sub_rng(self.seed, tid)
            freq = rng.choice(["biweekly", "weekly", "semi-monthly"]) if d != "easy" else "biweekly"
            first = fixed(rng, frequency=freq)
            stubs = [first]
            for _ in range(3 if d == "hard" else 2):
                stubs.append(next_stub(stubs[-1]))
            start = first.pay_date - timedelta(days=4)
            end = stubs[-1].pay_date + timedelta(days=5)
            no_pay = i in (4, 9)  # negative case: statement shows no payroll deposits at all
            st = bs.make_statement(rng, first.employee, first.employer, [] if no_pay else stubs, start=start, end=end,
                                   n_noise={"easy": 8, "medium": 20, "hard": 40}[d])
            if d == "hard":  # near-miss distractor: a person-to-person credit close to the net pay
                st.txns.append(bs.Txn(start + timedelta(days=9), "P2P PAYMENT RECEIVED " + "MARCUS BELLAMY",
                                      ps.r2(first.net * 0.98), "p2p"))
                st.txns.sort(key=lambda t: (t.day, t.desc))
                st.closing = ps.r2(st.opening + sum(t.amount for t in st.txns))
            if d == "easy":
                st.layout = 0
            pdf, txt = self.write_statement(tid, 1, st)
            deposits = [{"date": _iso(t.day), "amount": t.amount} for t in st.income_deposits]
            expected = {"account_holder": st.holder, "period_start": _iso(st.period_start),
                        "period_end": _iso(st.period_end), "income_deposits": deposits,
                        "closing_balance": st.closing}
            self.add(id=tid, category="B", difficulty=d, documents=[pdf], text_documents=[txt],
                     prompt_template="extract_bank_v1", expected=expected,
                     grading=[GradeSpec(method="exact", fields=list(expected))],
                     tags=["statement", f"{len(deposits)}-deposits"] + (["distractor-deposit"] if d == "hard" else []) + (["not-present"] if no_pay else []),
                     plain_title=f"Find the payroll deposits on a bank statement ({len(deposits)} paychecks among other activity)" if deposits else "Check a bank statement that has no payroll deposits",
                     why_it_matters="Bank statements show whether the income on pay stubs actually arrives. Only employer payroll deposits count, not transfers or refunds.",
                     what_good_looks_like="Lists exactly the payroll deposits with the right dates and amounts, and ignores transfers, refunds and payments from people.")

    def cat_c(self, n: int = 10) -> None:
        diffs = ["easy"] * 3 + ["medium"] * 4 + ["hard"] * 3
        for i in range(n):
            tid, d = f"calc-{i + 1:03d}", diffs[i]
            rng = _sub_rng(self.seed, tid)
            freq = ["biweekly", "weekly", "monthly", "semi-monthly"][i % 4]
            s = ps.make_stub(rng, frequency=freq, overtime=d != "easy" and rng.random() < .6, bonus=d == "hard" or (d == "medium" and i % 2 == 0))
            lay = ps.STUB_LAYOUTS[0] if d == "easy" else rng.choice(ps.STUB_LAYOUTS)
            pdf, txt = self.write_stub(tid, 1, s, lay)
            expected = {"pay_frequency": s.frequency, "bonus_included": False, "monthly_income": ps.monthly_income(s)}
            self.add(id=tid, category="C", difficulty=d, documents=[pdf], text_documents=[txt],
                     prompt_template="income_v1", expected=expected,
                     grading=[GradeSpec(method="exact", fields=["monthly_income"], tolerance=0.51),
                              GradeSpec(method="rubric", rubric=[
                                  RubricItem(id="freq", text="Uses the pay frequency printed on the stub", check=f"field_equals:pay_frequency={s.frequency}"),
                                  RubricItem(id="bonus", text="Does not count a one-time bonus", check="field_equals:bonus_included=false")])],
                     tags=[s.frequency] + (["bonus"] if s.bonus else []) + (["overtime"] if s.overtime_pay else []),
                     plain_title=f"Work out monthly income from a {s.frequency} pay stub" + (" that includes a one-time bonus" if s.bonus else ""),
                     why_it_matters="Lenders turn each paycheck into a monthly figure. Mixing up the frequency or counting a one-time bonus changes the answer.",
                     what_good_looks_like="Right pay frequency, bonus left out, monthly total within about 50 cents of the reference.")

    def cat_d(self, n: int = 8) -> None:
        plan = [("easy", []), ("easy", ["second_pay_stub"]), ("medium", []), ("medium", ["statement_coverage"]),
                ("medium", ["name_mismatch"]), ("hard", ["second_pay_stub", "name_mismatch"]),
                ("hard", ["statement_coverage", "name_mismatch"]), ("hard", [])]
        for i in range(n):
            tid, (d, gaps) = f"pack-{i + 1:03d}", plan[i]
            rng = _sub_rng(self.seed, tid)
            freq = rng.choice(["biweekly", "weekly", "semi-monthly"])
            a = fixed(rng, frequency=freq)
            b = next_stub(a)
            stubs = [a] if "second_pay_stub" in gaps else [a, b]
            holder = a.employee
            if "name_mismatch" in gaps:
                from . import names
                holder = names.person(rng)
                while holder == a.employee:
                    holder = names.person(rng)
            start, end = a.pay_date - timedelta(days=6), b.pay_date + timedelta(days=6)
            if "statement_coverage" in gaps:
                end = a.pay_date + timedelta(days=2)  # statement stops before the second pay date
            st = bs.make_statement(rng, holder, a.employer, [a, b], start=start, end=end, n_noise=14)
            lays = [ps.STUB_LAYOUTS[0]] if d == "easy" else [rng.choice(ps.STUB_LAYOUTS) for _ in stubs]
            docs, texts = [], []
            for j, s in enumerate(stubs):
                p, t = self.write_stub(tid, j + 1, s, lays[min(j, len(lays) - 1)])
                docs.append(p), texts.append(t)
            p, t = self.write_statement(tid, len(stubs) + 1, st)
            docs.append(p), texts.append(t)
            complete = not gaps
            words = {"second_pay_stub": "only one pay stub is included", "statement_coverage": "the bank statement ends before the second pay date",
                     "name_mismatch": "the name on the bank statement differs from the name on the pay stub"}
            ref = "The package is complete." if complete else "Not complete: " + "; ".join(words[g] for g in gaps) + "."
            expected = {"complete": complete, "missing": gaps, "explanation": ref}
            kw = {"second_pay_stub": ["one pay stub", "second pay stub", "second stub", "only one"],
                  "statement_coverage": ["statement ends", "does not cover", "second pay date", "coverage", "before"],
                  "name_mismatch": ["name"]}
            self.add(id=tid, category="D", difficulty=d, documents=docs, text_documents=texts,
                     prompt_template="completeness_v1", expected=expected,
                     grading=[GradeSpec(method="rubric", rubric=[
                         RubricItem(id="verdict", text="Says whether the package is complete correctly", weight=2, check=f"field_equals:complete={str(complete).lower()}"),
                         RubricItem(id="gaps", text="Lists exactly the missing items", weight=2, check="set_equals:missing"),
                         RubricItem(id="plain", text="Explains the gap in plain words and invents no documents", weight=1,
                                    check="judge:" + ref)],
                         judge_keywords=[k for g in gaps for k in kw[g]], judge_notes=ref)],
                     tags=["completeness"] + gaps,
                     plain_title="Check whether an income package is complete" + (" (it is)" if complete else " (something is off)"),
                     why_it_matters="A package with a missing stub or a mismatched name has to go back to the borrower. Catching it early saves a loop.",
                     what_good_looks_like="Correct complete/incomplete call, the exact problems named, and an explanation anyone could follow.")

    def cat_e(self, n: int = 10) -> None:
        plan = [("easy", "ytd_mismatch"), ("easy", "net_math"), ("easy", None), ("medium", "dates_out_of_order"),
                ("medium", "deposit_mismatch"), ("medium", None), ("medium", "employer_mismatch"),
                ("hard", "net_math"), ("hard", None), ("hard", "deposit_mismatch")]
        for i in range(n):
            tid, (d, code) = f"check-{i + 1:03d}", plan[i]
            rng = _sub_rng(self.seed, tid)
            s = fixed(rng, frequency=rng.choice(["biweekly", "weekly", "semi-monthly"]))
            with_statement = code in inc.NEEDS_STATEMENT or (code is None and i % 2 == 1)
            st = bs.make_statement(rng, s.employee, s.employer, [s], start=s.pay_date - timedelta(days=10),
                                   end=s.pay_date + timedelta(days=12), n_noise=12 if d != "hard" else 30) if with_statement else None
            if code in inc.STUB_ONLY:
                inc.inject_stub(s, code, rng)
            elif code:
                inc.inject_statement(st, s, code, rng)
            lay = ps.STUB_LAYOUTS[0] if d == "easy" else rng.choice(ps.STUB_LAYOUTS)
            docs, texts = [], []
            p, t = self.write_stub(tid, 1, s, lay)
            docs.append(p), texts.append(t)
            if st:
                p, t = self.write_statement(tid, 2, st)
                docs.append(p), texts.append(t)
            ref = ("The documents agree with each other and the arithmetic adds up." if not code else inc.DEFECTS[code])
            expected = {"verdict": "inconsistent" if code else "consistent", "issues": [code] if code else [], "explanation": ref}
            kw = {"ytd_mismatch": ["year-to-date", "ytd"], "net_math": ["net pay", "net"], "dates_out_of_order": ["date", "period"],
                  "deposit_mismatch": ["deposit"], "employer_mismatch": ["employer"]}
            self.add(id=tid, category="E", difficulty=d, documents=docs, text_documents=texts,
                     prompt_template="consistency_v1", expected=expected,
                     grading=[GradeSpec(method="exact", fields=["verdict", "issues"], weight=2),
                              GradeSpec(method="judge", judge_question="Does the explanation point to the specific inconsistency (or correctly say there is none), without calling the document fake or fraudulent?",
                                        judge_notes=ref, judge_keywords=kw.get(code, []))],
                     tags=["consistency"] + ([code] if code else ["clean"]) + (["stub+statement"] if st else ["stub-only"]),
                     plain_title="Spot contradictions inside the documents" if code else "Confirm clean documents are not flagged",
                     why_it_matters="Documents that disagree with themselves need a human look. Flagging clean documents wastes time too, so both mistakes count.",
                     what_good_looks_like="Flags the specific mismatch with the numbers or dates involved, or says everything checks out. Never accuses anyone of fraud.")

    def finish(self) -> dict:
        # dev/test split: every 5th task within each category goes to test (about 20%)
        counts: dict[str, int] = {}
        for t in self.tasks:
            counts[t.category] = counts.get(t.category, 0) + 1
            t.split = "test" if counts[t.category] % 5 == 0 else "dev"
        with (self.out / "tasks.jsonl").open("w") as f:
            for t in self.tasks:
                f.write(json.dumps(t.model_dump(), sort_keys=True) + "\n")
        manifest = {
            "name": TASKSET, "generator_version": GENERATOR_VERSION, "seed": self.seed,
            "task_count": len(self.tasks),
            "by_category": {c: sum(t.category == c for t in self.tasks) for c in "ABCDE"},
            "by_difficulty": {d: sum(t.difficulty == d for t in self.tasks) for d in ("easy", "medium", "hard")},
            "by_split": {s: sum(t.split == s for t in self.tasks) for s in ("dev", "test")},
            "not_present_tasks": sum("not-present" in t.tags for t in self.tasks),
            "synthetic": True,
            "note": "Every document is synthetic. See NOTICE.md.",
        }
        (self.out / "manifest.yaml").write_text(yaml.safe_dump(manifest, sort_keys=True))
        return manifest


def build(seed: int, out: Path) -> dict:
    if out.exists():
        shutil.rmtree(out)
    (out / "docs").mkdir(parents=True)
    b = Builder(seed, out)
    b.cat_a(), b.cat_b(), b.cat_c(), b.cat_d(), b.cat_e()
    return b.finish()
