# Agent skills

The skills live in `skills/`. Each is one `SKILL.md` that tells a coding agent how to operate the `evalpond` command line for someone who has good instincts about failures and has not built evals before.

## Install

```bash
npx skills add https://github.com/bnovarini/evalpond                              # all four
npx skills add https://github.com/bnovarini/evalpond --skill evalpond-write-tasks   # one
```

Claude Code plugin: `/plugin marketplace add bnovarini/evalpond`, then `/plugin install evalpond@evalpond`. The plugin files are `.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json`.

The agent also needs the CLI: `pip install git+https://github.com/bnovarini/evalpond` (Python 3.11 or newer). The start skill checks this.

## The flow

```
failure modes you already know  ->  evalpond-write-tasks  ->  tasksets/mine/  (validated)
                                                                   |
                          evalpond-run-and-explain  <--------------+
                                   |
                          plain-language answer: is it good, what matters, what first
                                   |
                          evalpond-audit-run  ->  can I trust it?
```

## What each skill does

- **evalpond-start**: routes. One table, one question at most.
- **evalpond-write-tasks**: accepts an edge-case list, a risk section or a demo bug report. Per failure mode it asks three things (what the AI gets, what it should say, how to check it mechanically), picks the cheapest check, then calls `add-task` and `validate`. Tasks are refused when the answer key and the grader disagree, when the wrong answer would still pass, or when the text contains personal data.
- **evalpond-run-and-explain**: validates, checks the key is set without printing it, runs with a cost cap, then reads `evalpond explain --json` and answers in plain words. Reports the plausible range for the pass rate, ranks failures by the severity you set, and refuses to call a gap inside the noise an improvement.
- **evalpond-audit-run**: ten checks, in priority order, on a finished run.

## CLI additions the skills rely on

| Command | Purpose |
|---|---|
| `evalpond add-task` | Add one task from flags or `--from-json`. Checked before writing. `--failure-mode`, `--severity`, `--exact`, `--check`, `--judge-question`, `--dry-run` |
| `evalpond validate TASKSET [--json]` | Schema, files, prompts, grader sanity. Self-tests every non-AI-graded task: a perfect answer must pass and a deliberately wrong one must fail. Warns about thin coverage and answer keys that are not in the document |
| `evalpond explain RUN [--json]` | Pass rate with range, by failure mode, what kind of mistake dominates, weakest answers, what to fix first, caveats |

`evalpond run` now defaults to a $2 cost cap for real models and refuses to run one without `price_in` and `price_out` in `models.yaml`, because a cap cannot work without prices. Use `--no-cost-cap` to opt out on purpose.

## Boundaries

- Made-up data only. See [NOTICE.md](../NOTICE.md).
- Keys are read from environment variables. Skills never ask for, print or store them.
- Nothing here has been run against a real model by the skill authors. The mock models exercise the pipeline, not model quality.
