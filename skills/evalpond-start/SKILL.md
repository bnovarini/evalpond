---
name: evalpond-start
description: >
  Entry point for evalpond, a small eval tool for LLM features. Use when someone
  has good instincts about how an AI feature fails but does not know how to turn
  that into evals or how to read the results. Routes to write-tasks,
  run-and-explain or audit-run. Skip it when the request already names one of those.
---

# evalpond start

The person you are helping probably has good judgment about failures and no idea how to turn it into evals or read what comes back. That is the gap evalpond closes. You operate the tool for them. You do not teach a course.

## Route in one step

Find the row that fits, say in one sentence which skill you are loading and why, then load it.

| What the person has | Load |
|---|---|
| Edge cases, a risk list, a PRD section, notes on what broke in a demo, but no tasks yet | `evalpond-write-tasks` |
| A task set (or the built-in sample) and wants to know "is this model good?" | `evalpond-run-and-explain` |
| Run results they are not sure they can trust, or a number someone is about to act on | `evalpond-audit-run` |
| Nothing yet, just curiosity | run `evalpond quickstart` (no keys, no cost), then ask which failure they worry about |

If two rows fit, ask one question. If none fits, say what evalpond can do (write tasks from failure modes, run them, explain results, audit a run) and ask which one they want.

## Setup check, once

1. `evalpond --version`. If it is missing: `pip install git+https://github.com/bnovarini/evalpond` (Python 3.11 or newer).
2. Look for an existing task set (`tasksets/` or a folder with `tasks.jsonl`). Use it instead of starting a new one.

## Ground rules that apply to every evalpond skill

- **Made-up data only.** Tasks use invented examples. If the person pastes real customer text, ask them to rewrite it with fake names and numbers. `evalpond add-task` rejects emails, phone numbers and ID numbers.
- **Keys never go in chat.** API keys live in environment variables the person sets themselves. Never ask for a key, never print one, never write one into a file you create.
- **Cost cap stays on.** Real-model runs always carry `--cost-cap`. Do not raise it without being told a number.
- **Plain words.** Say "answers" and "tasks", not "TPR" or "p-values". The CLI output already uses plain words; relay it.
- **Say what you did not test.** If a conclusion rests on 20 tasks, say so.
