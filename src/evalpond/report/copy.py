"""All reader-facing report copy lives here, so it can be checked for jargon in one place.

PLAIN strings appear in the main view. DETAILS strings appear only inside "Details for the curious".
"""
from __future__ import annotations

BANNED_IN_PLAIN = ["wilson", "mcnemar", "kappa", "bootstrap", "p-value", "confidence interval", "paired",
                   "discordant", "pearson", "standard error", "null hypothesis"]

# One-line explainers shown next to every statistic.
PLAIN = {
    "pass_rate": "Share of tasks answered completely right. One wrong field means the task counts as wrong.",
    "range": "The range the true pass rate probably falls in. A wide range means: do not read much into small gaps.",
    "avg_score": "Average partial credit per task. A task with 3 of 4 fields right earns 0.75 here.",
    "flaky": "Tasks that came out right in some repeats and wrong in others. The answer is not stable.",
    "cost": "Estimated spend for this run, from the prices set in models.yaml. Zero if no prices are set.",
    "latency": "Average seconds the model took per answer.",
    "fixed": "Wrong before, right now.",
    "regressed": "Right before, wrong now. These are the ones to look at first.",
    "luck": "Chance a gap this big would show up even if the two runs were equally good.",
    "heatmap": "Each row is a task, each column a run. Green is right, red is wrong. Rows with mixed colors tell the runs apart. All green or all red rows tell you nothing.",
    "judge_agree": "How often the AI grader agrees with a human on the same answers.",
    "judge_length": "Whether the AI grader favors longer answers. Near zero is what you want.",
    "split": "Dev tasks are for tuning prompts. Test tasks are held back, so they show whether tuning only helped on tasks you looked at.",
}

DETAILS = {
    "range": "95% Wilson score interval on the pass rate.",
    "luck": "Two-sided exact McNemar test on the tasks whose result flipped between the runs. Tasks that did not flip carry no information.",
    "judge_agree": "Cohen's kappa between the AI grader and human labels. 1 is perfect agreement, 0 is no better than chance.",
    "judge_length": "Pearson correlation between answer length and the AI grader's score.",
    "avg_score": "Mean of the weighted task scores, where each grader contributes its weight.",
    "gap": "A rough minimum gap two runs of this size can tell apart from luck: 1.96 x sqrt(2 p (1 - p) / n) at p = 0.8.",
}

VERDICT_WORDS = {"likely better": "looks better", "likely worse": "looks worse", "no clear difference": "shows no clear difference"}


def pct(x: float) -> str:
    return f"{x * 100:.0f}%"


def compare_sentence(a: str, b: str, c) -> str:
    fixed, reg = len(c.fixed), len(c.regressed)
    flips = f"{b} fixed {fixed} task{'s' if fixed != 1 else ''} and broke {reg}."
    if c.verdict == "no clear difference":
        return (f"{b} shows no clear difference from {a}. {flips} "
                f"That is about what luck alone would produce with {c.n} tasks.")
    word = "better" if c.verdict == "likely better" else "worse"
    return f"{b} looks {word} than {a}. {flips} A gap this size is unlikely to be luck."


def advice(c, a: str, b: str, hard_regressions: list[str]) -> str:
    if c.verdict == "likely worse" or (c.regressed and c.verdict != "likely better"):
        first = ", ".join(c.regressed[:3])
        return f"Look at the {len(c.regressed)} regression{'s' if len(c.regressed) != 1 else ''} first, starting with {first}. Open each one to see what changed in the answer."
    if c.verdict == "likely better":
        extra = f" Still check the {len(c.regressed)} task{'s' if len(c.regressed) != 1 else ''} it got worse on." if c.regressed else ""
        return f"Safe to prefer {b} on accuracy.{extra}"
    return (f"Do not choose between {a} and {b} on accuracy from this set. Decide on cost and speed, "
            f"or add more tasks that tell the two apart.")
