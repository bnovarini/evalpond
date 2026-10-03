"""Builds the prd_v1 task set: synthetic product requirement documents (PRDs) and summary tasks.

Every PRD is generated from invented feature blueprints. Nothing is copied from a real company or product.
Grading is programmatic (key-phrase and number checks), so the set runs with no AI grader.
Same seed gives a byte-identical set.
"""
from __future__ import annotations

import json
import random
import re
import shutil
from pathlib import Path

import yaml

from ..schema import GradeSpec, RubricItem, Task

TASKSET = "prd_v1"
GENERATOR_VERSION = "1"
CATEGORY_NAMES = {"F": "Summarize a PRD", "G": "Say what is out of scope", "H": "Handle a PRD with a gap"}
MAX_WORDS = 120

# Each blueprint: a made-up feature. Items are (text, key phrases separated by |).
BLUEPRINTS = [
    dict(title="Pickup Reminders for Parcel Lockers", team="Lockers team", problem="Customers forget parcels in lockers, and full lockers turn new deliveries away.",
         goals=[("cut the share of parcels left uncollected after 3 days", "uncollected|left in the locker"), ("free up locker space at busy sites", "space|capacity")],
         metric=("Uncollected-after-3-days rate", "uncollected", (15, 24), (6, 11)),
         in_scope=[("text and push reminders at 24 and 48 hours", "reminders at 24"), ("a quiet-hours setting", "quiet hours")],
         out_scope=[("email reminders", "email"), ("changes to locker pricing", "pricing"), ("reminders for business accounts", "business accounts")],
         reqs=[("reminder timing can be set per site", "per site|timing"), ("customers can opt out in one tap", "opt out|opt-out")],
         rejected=("automatically returning parcels to the sender after 5 days", "returning parcels|return parcels|sender")),
    dict(title="Offline Mode for the Field Inspection App", team="Field Apps team", problem="Inspectors lose work when the signal drops inside buildings.",
         goals=[("let inspectors finish a report with no signal", "no signal|offline"), ("stop lost or duplicated reports", "lost|duplicate")],
         metric=("Reports lost or duplicated per 1,000", "lost|duplicat", (30, 48), (4, 9)),
         in_scope=[("saving checklists and photos on the device", "photos"), ("automatic sync when the signal returns", "sync")],
         out_scope=[("offline map tiles", "map"), ("editing reports from two devices at once", "two devices|simultaneous"), ("a desktop version", "desktop")],
         reqs=[("a visible badge shows what has not synced yet", "badge|not synced|unsynced"), ("sync retries without user action", "retr")],
         rejected=("a paid add-on for extra offline storage", "paid add-on|extra offline storage")),
    dict(title="Saved Searches and Alerts for the Recipe Library", team="Discovery team", problem="Cooks re-run the same searches and miss new recipes that match.",
         goals=[("bring cooks back when new matching recipes appear", "come back|return|re-engag|bring"), ("make repeat searches faster", "faster|repeat")],
         metric=("Weekly returning-cook rate", "returning", (22, 30), (34, 41)),
         in_scope=[("saving a search with its filters", "saving a search|saved search"), ("a weekly digest of new matches", "digest")],
         out_scope=[("real-time push alerts", "push"), ("sharing saved searches with other people", "sharing"), ("search by ingredient photo", "photo")],
         reqs=[("each cook can keep up to 20 saved searches", "20 saved"), ("the digest can be paused at any time", "paused|pause")],
         rejected=("a public leaderboard of most-saved searches", "leaderboard")),
    dict(title="Self-Serve Plan Changes for Small Teams", team="Billing Experience team", problem="Small teams email support to add seats or switch plans, and wait a day for an answer.",
         goals=[("let team admins change seats and plans without contacting support", "without contacting support|self-serve|themselves"), ("cut plan-change support tickets", "tickets|support")],
         metric=("Plan-change tickets per week", "tickets", (210, 260), (60, 95)),
         in_scope=[("adding and removing seats", "seats"), ("switching between the two paid plans", "paid plans|switch")],
         out_scope=[("custom enterprise contracts", "enterprise"), ("refunds", "refund"), ("annual-to-monthly downgrades", "annual")],
         reqs=[("admins see the new price before they confirm", "price|before they confirm"), ("a receipt is emailed after each change", "receipt")],
         rejected=("a discount for switching plans mid-month", "discount")),
    dict(title="Shift Swap Requests for Clinic Schedulers", team="Scheduling team", problem="Staff arrange shift swaps by text, and managers learn about them late.",
         goals=[("let staff request swaps inside the schedule", "inside the schedule|request swaps|in the app"), ("give managers one place to approve them", "approve|one place")],
         metric=("Swaps approved within 24 hours", "approved|24 hours", (35, 48), (75, 88)),
         in_scope=[("swap requests between two staff members", "swap requests"), ("manager approval with a one-line reason", "approval")],
         out_scope=[("open-shift bidding", "bidding|open-shift"), ("overtime rules", "overtime"), ("swaps across clinics", "across clinics")],
         reqs=[("both staff members must accept before the manager is asked", "accept"), ("approved swaps update the schedule at once", "update the schedule|schedule")],
         rejected=("letting staff trade shifts without approval", "without approval")),
    dict(title="Delivery Window Picker for Grocery Orders", team="Checkout team", problem="Shoppers abandon checkout when the delivery windows are unclear.",
         goals=[("make delivery windows clear before payment", "clear|windows"), ("reduce checkout abandonment", "abandon")],
         metric=("Checkout abandonment rate", "abandon", (27, 35), (18, 24)),
         in_scope=[("a two-hour window picker", "window picker|two-hour"), ("showing the delivery fee next to each window", "fee")],
         out_scope=[("same-day rush delivery", "rush|same-day"), ("driver tipping", "tipping|tip"), ("pickup orders", "pickup")],
         reqs=[("full windows are shown as unavailable, not hidden", "unavailable|not hidden|full windows"), ("the chosen window is kept if the cart changes", "kept|cart")],
         rejected=("auction-style pricing for popular windows", "auction")),
]
MONTHS = ["March", "April", "May", "June", "September", "October", "November"]
OWNERS = ["Mira", "Dev", "Tamsin", "Okafor", "Lena", "Ravi", "Sol"]
FILLER = ("This summary covers every section of the document in the order it appears, restating each point at length so that no reader "
          "could possibly miss any detail or nuance that the authors wrote down, including background and process notes.")


def _nums(text: str) -> set[str]:
    return {n for n in re.findall(r"\d+(?:\.\d+)?", text.replace(",", ""))}


def _fmt_target(v: int) -> str:
    return f"{v}%"


def _make_prd(rng: random.Random, bp: dict, layout: str, noise: set[str], gap: str | None) -> tuple[str, dict]:
    base = rng.randint(*bp["metric"][2])
    target = rng.randint(*bp["metric"][3])
    pct = "%" if bp["metric"][0].endswith(("rate", "24 hours")) else ""
    old = target + 7 if target < base else target - 7
    month, year = rng.choice(MONTHS), rng.choice([2027, 2028])
    owner = rng.choice(OWNERS)
    ins, outs, reqs, goals = bp["in_scope"], bp["out_scope"], bp["reqs"], bp["goals"]
    mname = bp["metric"][0]
    mline = f"{mname}: from {base}{pct} today to {target}{pct} by launch."
    sections: dict[str, str] = {}
    if layout == "standard":
        sections["Overview"] = f"{bp['problem']} Owner: {owner}, {bp['team']}. Target launch: {month} {year}."
        sections["Goals"] = "\n".join(f"- {g[0].capitalize()}" for g in goals)
        if gap != "no_metrics":
            sections["Success metrics"] = f"- {mline}"
        sections["In scope"] = "\n".join(f"- {i[0].capitalize()}" for i in ins)
        if gap != "no_scope":
            sections["Out of scope"] = "\n".join(f"- {o[0].capitalize()}" for o in outs)
        sections["Requirements"] = "\n".join(f"{n + 1}. {r[0].capitalize()}" for n, r in enumerate(reqs))
        sections["Open questions"] = "- Which sites pilot first?\n- Who reviews copy before launch?"
    elif layout == "narrative":
        sections["Why now"] = f"{bp['problem']} {owner} from the {bp['team']} owns this, and the plan is to launch in {month} {year}."
        sections["What we want"] = "We want to " + " and to ".join(g[0] for g in goals) + "."
        if gap != "no_metrics":
            sections["How we will know"] = f"We will track {mline[0].lower() + mline[1:]}"
        sections["What is in"] = "The first version includes " + " and ".join(i[0] for i in ins) + "."
        if gap != "no_scope":
            sections["What is not in"] = "We are deliberately leaving out " + ", ".join(o[0] for o in outs[:-1]) + f", and {outs[-1][0]}."
        sections["What it must do"] = " ".join(f"It must satisfy this: {r[0]}." for r in reqs)
    else:  # terse
        sections["Summary"] = f"{bp['title']} | {owner} / {bp['team']} | launch {month} {year}\nProblem: {bp['problem']}"
        sections["Goals"] = "; ".join(g[0] for g in goals)
        if gap != "no_metrics":
            sections["Metric"] = mline
        sections["In"] = "; ".join(i[0] for i in ins)
        if gap != "no_scope":
            sections["Out"] = "; ".join(o[0] for o in outs)
        sections["Must have"] = "; ".join(r[0] for r in reqs)
    current = "\n".join(sections.values())
    allowed = sorted(_nums(current) | _nums(bp["title"]))
    extra: dict[str, str] = {}
    if "changelog" in noise and gap != "no_metrics":
        extra["Changelog"] = (f"- v0.3: the target for {mname.lower()} was changed from {old}{pct} to {target}{pct}.\n"
                              f"- v0.2: pilot sites narrowed from 12 to 5.\n- v0.1: first draft.")
    if "rejected" in noise:
        extra["Ideas we considered and dropped"] = f"- {bp['rejected'][0].capitalize()}. Dropped: it is not part of this work."
    if "appendix" in noise:
        extra["Appendix: research notes"] = (f"Interviews with {rng.randint(11, 19)} customers found that {rng.randint(41, 79)}% had hit this problem at least once. "
                                             f"A survey of {rng.randint(300, 900)} users showed {rng.randint(12, 38)}% would use it weekly. These are context, not targets.")
    body = f"# PRD: {bp['title']}\n\nStatus: example. All content is synthetic.\n\n"
    body += "\n\n".join(f"## {k}\n{v}" for k, v in {**sections, **extra}.items()) + "\n"
    facts = dict(base=base, target=target, pct=pct, old=old, month=month, year=year, mname=mname, allowed=allowed)
    return body, facts


def _summary(bp: dict, f: dict, parts: set[str]) -> str:
    out = []
    if "goals" in parts:
        out.append(f"Goals: {bp['goals'][0][0]}; {bp['goals'][1][0]}.")
    if "metric" in parts:
        out.append(f"Success metric: {f['mname']} from {f['base']}{f['pct']} to {f['target']}{f['pct']}.")
    if "scope" in parts:
        out.append("Out of scope: " + ", ".join(o[0] for o in bp["out_scope"]) + ".")
    if "reqs" in parts:
        out.append("Key requirements: " + "; ".join(r[0] for r in bp["reqs"]) + ".")
    return " ".join(out)


def _safe_in_keys(bp: dict) -> str:
    """Key phrases for in-scope items that do not also occur in goals, metric, requirements or out-of-scope text."""
    other = " ".join([g[0] for g in bp["goals"]] + [r[0] for r in bp["reqs"]] + [o[0] for o in bp["out_scope"]] + [bp["metric"][0]]).lower()
    keep = []
    for text, keys in bp["in_scope"]:
        cands = [k for k in keys.split("|") if k and k.lower() not in other] or [text]
        keep += cands
    return "|".join(keep)


def _any(keys: str) -> str:
    return "any_of:" + keys


def _target_forms(f: dict) -> str:
    t = f["target"]
    return f"{t}%|{t} percent|{t} %" if f["pct"] else f"{t}|{t:,}"


class Builder:
    def __init__(self, seed: int, out: Path):
        self.seed, self.out, self.tasks = seed, out, []

    def _write(self, tid: str, text: str) -> str:
        rel = f"docs/{tid}-prd.md"
        (self.out / rel).write_text(text)
        return rel

    def add(self, **kw) -> None:
        self.tasks.append(Task(**kw))

    def cat_f(self, n: int = 20) -> None:
        plan = [("easy", "standard", set()), ("easy", "narrative", set()), ("easy", "terse", set()), ("medium", "standard", {"changelog"}),
                ("medium", "narrative", {"rejected"}), ("medium", "terse", {"changelog"}), ("medium", "standard", {"rejected", "changelog"}),
                ("hard", "narrative", {"changelog", "rejected", "appendix"}), ("hard", "terse", {"changelog", "rejected", "appendix"}),
                ("hard", "standard", {"changelog", "rejected", "appendix"})]
        for i in range(n):
            d, layout, noise = plan[i % len(plan)]
            tid = f"prd-sum-{i + 1:03d}"
            rng = random.Random(f"{self.seed}:{tid}")
            bp = BLUEPRINTS[i % len(BLUEPRINTS)]
            text, f = _make_prd(rng, bp, layout, noise, None)
            ref = _summary(bp, f, {"goals", "metric", "scope", "reqs"})
            variants = [_summary(bp, f, {"goals", "scope", "reqs"}), _summary(bp, f, {"goals", "metric", "reqs"}),
                        ref + f" Expected to save ${rng.randint(2, 9)}.{rng.randint(1, 9)}M a year.",
                        ref + f" It also adds {bp['rejected'][0]}.",
                        ref.replace(f"to {f['target']}{f['pct']}", f"to {f['old']}{f['pct']}") if "changelog" in noise else ref.replace(f"to {f['target']}{f['pct']}", f"to {f['target'] * 2 + 3}{f['pct']}"),
                        ref + " " + FILLER * 2]
            mname_key = bp["metric"][1]
            rub = [RubricItem(id="goal1", text="States the first goal", weight=1, check=_any(bp["goals"][0][1])),
                   RubricItem(id="goal2", text="States the second goal", weight=1, check=_any(bp["goals"][1][1])),
                   RubricItem(id="metric", text="Names the success metric", weight=1, check=_any(mname_key)),
                   RubricItem(id="target", text="Gives the current target number", weight=2, check=_any(_target_forms(f))),
                   RubricItem(id="scope", text="Says what is out of scope", weight=1, check=_any("|".join(o[1] for o in bp["out_scope"]))),
                   RubricItem(id="req", text="Mentions a key requirement", weight=1, check=_any("|".join(r[1] for r in bp["reqs"]))),
                   RubricItem(id="no_invented", text="Uses no number that is not in the current requirements", weight=2, check="numbers_subset:"),
                   RubricItem(id="no_rejected", text="Does not present a dropped idea as part of the plan", weight=2, check="none_of:" + bp["rejected"][1]),
                   RubricItem(id="short", text=f"Stays within {MAX_WORDS} words", weight=1, check=f"max_words:{MAX_WORDS}")]
            self.add(id=tid, category="F", difficulty=d, text_documents=[self._write(tid, text)], prompt_template="prd_summary_v1",
                     expected={"summary": ref, "allowed_numbers": f["allowed"], "mock_variants": variants},
                     grading=[GradeSpec(method="rubric", rubric=rub)], tags=["summary", layout] + sorted(noise),
                     plain_title=f"Summarize the PRD for \"{bp['title']}\"" + (" (has an old target in the changelog)" if "changelog" in noise else ""),
                     why_it_matters="Leaders read the summary, not the PRD. A summary that drops the metric, uses an old number, or adds a feature that was dropped sends people in the wrong direction.",
                     what_good_looks_like="Short, covers goals, the metric and its current target, what is out of scope and the key requirements, and invents nothing.")

    def cat_g(self, n: int = 10) -> None:
        plan = ["easy", "easy", "easy", "medium", "medium", "medium", "medium", "hard", "hard", "hard"]
        for i in range(n):
            d = plan[i % len(plan)]
            tid = f"prd-scope-{i + 1:03d}"
            rng = random.Random(f"{self.seed}:{tid}")
            bp = BLUEPRINTS[(i + 2) % len(BLUEPRINTS)]
            noise = {"easy": set(), "medium": {"rejected"}, "hard": {"rejected", "changelog", "appendix"}}[d]
            layout = ["standard", "narrative", "terse"][i % 3]
            text, f = _make_prd(rng, bp, layout, noise, None)
            ref = "Out of scope: " + ", ".join(o[0] for o in bp["out_scope"]) + "."
            variants = [("Out of scope: " + ", ".join(o[0] for o in bp["out_scope"][:-1]) + "."),
                        ref + f" Also out: {bp['in_scope'][0][0]}.", ref + f" Also out: {bp['rejected'][0]}.",
                        f"Out of scope: {bp['in_scope'][1][0]}, " + ", ".join(o[0] for o in bp["out_scope"][:1]) + "."]
            rub = [RubricItem(id=f"out{j + 1}", text=f"Lists: {o[0]}", weight=1, check=_any(o[1])) for j, o in enumerate(bp["out_scope"])]
            rub += [RubricItem(id="no_in_scope", text="Does not list an in-scope item as out of scope", weight=2,
                               check="none_of:" + _safe_in_keys(bp)),
                    RubricItem(id="no_rejected", text="Does not list a dropped idea as the plan's scope", weight=1, check="none_of:" + bp["rejected"][1]),
                    RubricItem(id="no_invented", text="Uses no number that is not in the document", weight=1, check="numbers_subset:"),
                    RubricItem(id="short", text="Stays within 60 words", weight=1, check="max_words:60")]
            self.add(id=tid, category="G", difficulty=d, text_documents=[self._write(tid, text)], prompt_template="prd_scope_v1",
                     expected={"summary": ref, "allowed_numbers": f["allowed"], "mock_variants": variants},
                     grading=[GradeSpec(method="rubric", rubric=rub)], tags=["scope", layout] + sorted(noise),
                     plain_title=f"List what is out of scope in \"{bp['title']}\"",
                     why_it_matters="Scope creep starts when people disagree about what was never promised. The out-of-scope list is the part readers need most and models skim past.",
                     what_good_looks_like="Exactly the items the PRD rules out. No in-scope items, no dropped ideas, nothing made up.")

    def cat_h(self, n: int = 10) -> None:
        for i in range(n):
            gap = "no_metrics" if i % 2 == 0 else "no_scope"
            d = ["easy", "medium", "hard"][i % 3] if i < 9 else "hard"
            tid = f"prd-gap-{i + 1:03d}"
            rng = random.Random(f"{self.seed}:{tid}")
            bp = BLUEPRINTS[(i + 4) % len(BLUEPRINTS)]
            noise = {"easy": set(), "medium": {"rejected"}, "hard": {"rejected", "appendix"}}[d]
            layout = ["standard", "narrative", "terse"][(i + 1) % 3]
            text, f = _make_prd(rng, bp, layout, noise, gap)
            allowed = set(f["allowed"])
            invented = next(x for x in (str(rng.randint(11, 59)) for _ in range(50)) if x not in allowed)
            if gap == "no_metrics":
                parts = {"goals", "scope", "reqs"}
                ack = "any_of:not stated|no metric|no success metric|not defined|not specified|does not state|does not specify|doesn't specify|doesn't state|missing|not provided|no target"
                ref = _summary(bp, f, parts) + " Success metric: not stated in the document."
                variants = [_summary(bp, f, parts), _summary(bp, f, parts) + f" Success metric: reduce the problem by {invented}%.",
                            _summary(bp, f, parts) + f" Target: {invented} percent improvement."]
                what = "success metric"
            else:
                parts = {"goals", "metric", "reqs"}
                ack = "any_of:not stated|no out-of-scope|no non-goals|not defined|not specified|does not state|does not specify|doesn't specify|doesn't state|missing|not provided|nothing about scope|no scope"
                ref = _summary(bp, f, parts) + " Out of scope: not stated in the document."
                variants = [_summary(bp, f, parts), _summary(bp, f, parts) + f" Out of scope: {bp['out_scope'][0][0]}, {bp['rejected'][0]}.",
                            _summary(bp, f, parts) + f" Out of scope: {bp['in_scope'][0][0]}."]
                what = "out-of-scope list"
            rub = [RubricItem(id="goal1", text="States the first goal", weight=1, check=_any(bp["goals"][0][1])),
                   RubricItem(id="flags_gap", text=f"Says the {what} is missing instead of guessing", weight=3, check=ack),
                   RubricItem(id="no_invented", text="Uses no number that is not in the document", weight=2, check="numbers_subset:"),
                   RubricItem(id="short", text=f"Stays within {MAX_WORDS} words", weight=1, check=f"max_words:{MAX_WORDS}")]
            if gap == "no_scope":
                rub.append(RubricItem(id="no_made_up_scope", text="Does not invent an out-of-scope list from other sections", weight=2,
                                      check="none_of:" + _safe_in_keys(bp) + "|" + bp["rejected"][1]))
            else:
                rub.append(RubricItem(id="metric_name", text="Does not make up a metric target", weight=0, check=_any("not stated|no metric|no success metric|not defined|not specified|does not state|does not specify|doesn't specify|doesn't state|missing|not provided|no target")))
            self.add(id=tid, category="H", difficulty=d, text_documents=[self._write(tid, text)], prompt_template="prd_summary_v1",
                     expected={"summary": ref, "allowed_numbers": f["allowed"], "mock_variants": variants},
                     grading=[GradeSpec(method="rubric", rubric=rub)], tags=["gap", gap, layout] + sorted(noise),
                     plain_title=f"Summarize a PRD that has no {what}",
                     why_it_matters="A good summarizer says \"the document does not say\" when it does not. A weak one fills the gap with a plausible number, and someone repeats it in a meeting.",
                     what_good_looks_like=f"Summarizes what is there, says plainly that the {what} is missing, and makes nothing up.")

    def finish(self) -> dict:
        counts: dict[str, int] = {}
        for t in self.tasks:
            counts[t.category] = counts.get(t.category, 0) + 1
            t.split = "test" if counts[t.category] % 5 == 0 else "dev"
        with (self.out / "tasks.jsonl").open("w") as fh:
            for t in self.tasks:
                fh.write(json.dumps(t.model_dump(), sort_keys=True) + "\n")
        manifest = {
            "name": TASKSET, "generator_version": GENERATOR_VERSION, "seed": self.seed, "task_count": len(self.tasks),
            "categories": CATEGORY_NAMES, "topic": "summarizing product requirement documents",
            "by_category": {c: sum(t.category == c for t in self.tasks) for c in CATEGORY_NAMES},
            "by_difficulty": {d: sum(t.difficulty == d for t in self.tasks) for d in ("easy", "medium", "hard")},
            "by_split": {s: sum(t.split == s for t in self.tasks) for s in ("dev", "test")},
            "not_present_tasks": sum("gap" in t.tags for t in self.tasks),
            "synthetic": True, "note": "Every document is synthetic. See NOTICE.md.",
        }
        (self.out / "manifest.yaml").write_text(yaml.safe_dump(manifest, sort_keys=True))
        return manifest


def build(seed: int, out: Path) -> dict:
    if out.exists():
        shutil.rmtree(out)
    (out / "docs").mkdir(parents=True)
    b = Builder(seed, out)
    b.cat_f(), b.cat_g(), b.cat_h()
    return b.finish()
