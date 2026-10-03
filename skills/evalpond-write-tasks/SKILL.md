---
name: evalpond-write-tasks
description: >
  Turn a PM's edge cases, risk list, or "here is what broke in the demo" into
  validated evalpond tasks. Use when someone describes ways an AI feature can
  fail and wants evals for them, or asks how to get from failure modes to
  something the harness can run. Produces tasks that pass `evalpond validate`.
---

# Write tasks from failure modes

Input is whatever the person already has: an edge-case list, a risk section of a PRD, a Slack thread about a bad demo, screenshots of wrong answers. Output is a task set that `evalpond validate` accepts. They bring the judgment. You do the translation.

## 1. Collect failure modes (do not ask for a new document)

Read what they gave you. List the failure modes you find as short plain phrases ("invents a refund window", "too blunt with upset customers") and play the list back in one message. Ask only: "Anything missing? Which two would hurt users most?" Record each answer as `--severity high|medium|low`.

## 2. Interview per failure mode, three questions

For each mode, in the person's words:

1. **What does the AI get?** The input: a document, a ticket, a policy, a question. (Made up, short, realistic.)
2. **What should it say or do?** The right answer in one line. If the correct behavior is "say the input does not tell you", the expected value is `null`.
3. **How would you check it without reading every answer?** A field that must match, words that must appear or must not appear, a length limit. If they cannot say, use a judge question (last resort).

Offer a concrete guess for questions 2 and 3 from what you already read and let them correct it. Do not make them design the check.

## 3. Pick the check (cheapest that works)

| The failure is... | Use |
|---|---|
| A wrong value or decision | `--exact field` with `--expected '{"field": value}'` |
| Making something up when the input is silent | `--expected '{"field": null}' --exact field` (always include these) |
| Missing or forbidden content, too long | `--check "id|plain text|mentions:..."`, `any_of:a|b`, `none_of:a|b`, `max_words:N` |
| Tone or quality no rule can see | `--judge-question "Does the reply ...?"` and say it needs `--judge` and a hand check |

Read `references/checks.md` when unsure. Write 2 to 3 inputs per failure mode, including one near-miss that should pass and one where the input is silent.

## 4. Add, then validate

```
evalpond add-task --taskset tasksets/mine --failure-mode "Invents a refund window" \
  --severity high --question "How many days does the customer have to return an item?" \
  --input "Policy: returns accepted in store. Gift cards are final sale." \
  --expected '{"refund_days": null}' --exact refund_days \
  --why "A made-up promise costs money." --good "Says the policy does not state a window."
evalpond validate tasksets/mine
```

`add-task` checks before it writes and refuses on a problem. For many tasks, write a JSON file and use `--from-json` (it takes an `inputs` list). Add `--split test` to about one in five tasks and never tune against them.

Fix every ERROR. Read every warning to the person in one sentence each. The ones that matter most: a wrong answer that still passes ("cannot_fail"), an answer key not found in the input (usually a typo), too few tasks per failure mode.

## 5. Hand off

Say: how many tasks per failure mode, how many are checked mechanically, how many need an AI grader. Then offer to run them with `evalpond-run-and-explain`. A first dry run on `--model mock-weak` shows the pipeline works at no cost, but it says nothing about a real model.

## Do not

- Do not use real customer text, names, emails or numbers.
- Do not lecture on eval theory. One sentence of why, only when they ask.
- Do not write tasks for failures the person never mentioned. Suggest at most two more, labelled as suggestions.
- Do not add a task that `validate` flags as an error to "fix it later".
