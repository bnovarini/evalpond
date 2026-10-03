---
name: evalpond-run-and-explain
description: >
  Run an evalpond task set against a model and explain the result in plain
  words: is it good, which failures matter, what to fix first, and whether a
  difference is real or inside the noise. Use when someone asks how a model did,
  wants to compare two models or prompts, or has run results they cannot read.
---

# Run and explain

You operate the run, then answer three questions in plain words: **is this good enough, which failures matter, what do I fix first.** The numbers come from evalpond's own output. Do not invent any.

## 1. Before a real run

1. `evalpond validate <taskset>`. Stop on errors (use `evalpond-write-tasks` to fix them).
2. Pick the model from `models.yaml`. A real model needs `price_in` and `price_out` there (USD per million tokens, from the provider's current price page) or the cost cap cannot work and `run` refuses.
3. **Keys.** The model entry names an environment variable (`api_key_env`). Check it exists without printing it: `[ -n "$NAME" ] && echo set || echo missing`. If missing, tell the person to set it in their own terminal or shell profile. Do not ask them to paste it into chat, and do not write it into any file.
4. **Cost cap.** Always pass `--cost-cap`. Default $2 unless the person gave a number. Say the cap out loud before running. Tasks with an AI grader also need `--judge <other model>`; the grader must differ from the model under test.
5. Smoke test first when a taskset is new: `--model mock-strong` runs the whole pipeline free.

## 2. Run

```
evalpond run --model NAME --taskset tasksets/mine --cost-cap 2 --repeats 3
```

Use `--repeats 3` when comparing two things. A stopped run (cap hit, crash) is saved; rerun the same command to resume. Never raise the cap on your own to finish.

## 3. Explain

```
evalpond explain runs/<id>.json --taskset tasksets/mine --json
```

Read the JSON and answer in this order, in plain sentences:

1. **Is it good?** `pass_rate` with `pass_rate_range`. Say "X of Y answers fully right, and with this many tasks the true rate could be anywhere from A to B." Good enough depends on the cost of the failure, so ask what error rate they could live with if you do not know.
2. **Which failures matter?** `fix_first` (their severity ratings, then counts), then `by_category`. Name the failure modes the way the person named them.
3. **What first?** `patterns` tells what kind of mistake dominates: made something up, missed something that was there, wrong value, unreadable format, model error. Give one concrete next step for the top one (for example "change the prompt to say 'not stated' when the document is silent", or "these 3 tasks look mislabeled, check the key"). Quote one or two real failing answers from `failures`.

Then read `caveats` aloud, briefly. If `model_errors` is above zero, say the score is not trustworthy until those are fixed.

## 4. Comparing two runs

`evalpond compare runs/a.json runs/b.json`. Report the verdict as written. When it says "no clear difference", say so and what size of gap this many tasks could show. Never call a gap inside that range an improvement.

For the full picture offer `evalpond report runs --taskset tasksets/mine`, which writes one HTML file.

## Do not

- Do not call 85% versus 88% on 40 tasks a win.
- Do not average away a high-severity failure with good scores elsewhere.
- Do not read results out of the HTML report when `explain --json` has them.
- Do not print, echo or store a key. Do not run without a cap.
