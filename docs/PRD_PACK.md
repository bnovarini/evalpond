# The PRD summary pack (prd_v1)

All documents are synthetic. The products, teams, people and numbers are invented. See [NOTICE.md](../NOTICE.md).

## What it tests

A model reads a product requirements document (PRD) and writes a short summary. This is a common first AI feature on a product team, and an easy one to get quietly wrong.

| Kind of task | Count | What a good answer does |
|---|---|---|
| Summarize a PRD (F) | 20 | Covers goals, the metric and its current target, what is out of scope and key requirements, in 120 words or fewer |
| Say what is out of scope (G) | 10 | Lists exactly what the PRD rules out. No in-scope items, no dropped ideas |
| Handle a PRD with a gap (H) | 10 | Summarizes what is there and says "not stated" for the missing metric or scope list |

Difficulty comes from the document. Easy ones are clean. Medium ones add a changelog with an old target, or a "dropped ideas" section. Hard ones add both plus a research appendix full of tempting numbers.

## How answers are checked

No AI grader. Each task is a rubric of yes/no checks:

- **Has it:** a key phrase for each required element (any of a few wordings).
- **Made nothing up:** every number in the summary must appear in the PRD's current requirements. Whole numbers up to 10 are ignored.
- **No dropped ideas:** the summary must not present a rejected idea as part of the plan.
- **Short:** a word limit.
- **Flags the gap:** for the gap tasks, says the item is not stated.

Because these are phrase checks, a correct summary in unusual words can be marked wrong. That is a real limit. If you see it in a report, open the task, read the answer, and either add a wording to the task or switch that item to the AI grader (see [WRITING_TASKS.md](WRITING_TASKS.md)).

## Run it

```bash
uv run evalpond gen --pack prd
uv run evalpond run --model mock-strong --taskset tasksets/prd_v1 --out runs-prd
uv run evalpond report runs-prd --taskset tasksets/prd_v1 --out site-prd
```

The prompts are in `src/evalpond/prompts/prd_summary_v1.txt` and `prd_scope_v1.txt`. Change a word and the prompt hash changes, so reports show which wording a run used.
