---
name: evalpond-audit-run
description: >
  Check whether an evalpond result can be trusted before someone acts on it.
  Use when a number is about to drive a decision (ship, switch models, change a
  prompt), when results look too good or too bad, or when a judge model graded
  answers. Returns prioritized problems with the evidence.
---

# Audit a run

Short and skeptical. The goal is to find what would make the number misleading, ordered by how much it matters. Report findings, not a lecture.

## Gather (all read-only, no model calls)

```
evalpond validate <taskset> --json
evalpond explain runs/<id>.json --taskset <taskset> --json
```

Also look at the `models.yaml` entry used and whether `calibration/labels.jsonl` exists.

## Check, in this order

| # | Question | Where to look | Problem if |
|---|---|---|---|
| 1 | Did the model actually answer? | `model_errors`, patterns `unreadable_answer`, `model_error` | Any. The score is partly a plumbing score |
| 2 | Can the tasks fail? | validate warnings `cannot_fail`, `gold_fails` | Any. Those tasks say nothing |
| 3 | Is the answer key right? | validate `key_not_in_document`; read 3 failures in `failures` | The "wrong" answer is arguably right |
| 4 | Is the judge trusted? | `judge_model`; no `calibration/labels.jsonl` | Judge-graded results with no hand-labelled check |
| 5 | Same model grading itself? | `model` equals `judge_model` | Yes: graded too kindly |
| 6 | Enough tasks? | `answers`, `pass_rate_range`, validate `small_set`, `thin_category` | The range is wider than the decision needs |
| 7 | Single run? | `repeats`, `flaky_tasks` | One repeat, or many flaky tasks |
| 8 | Silent-input tasks included? | validate `few_not_present` | Models that invent look better than they are |
| 9 | Tuned on the test split? | `caveats` mentions dev and test mixed; prompt changed after seeing test | Yes |
| 10 | Does the average hide a high-severity failure? | `fix_first` | A high-severity mode is failing while the overall rate looks fine |

Read three failing answers and three passing ones in full before concluding anything. Real answers beat any summary.

## Report

One message: a verdict ("trust this number / trust it with these limits / do not act on it"), then the problems, most important first, each with the evidence (task ids, counts) and the fix (a command or a change). End with the single cheapest step that would most increase trust, such as `--repeats 3` or `evalpond calibrate`.

Never edit tasks or rerun a paid run as part of an audit without being asked. Keys and cost caps follow `evalpond-start`.
