# A short guide to evals, for product managers

All documents in this project are synthetic. See [NOTICE.md](../NOTICE.md).

## What an eval is

An eval is a unit test for behavior you cannot check with `output == expected`. You write a set of tasks, decide how each answer is scored, and run the set every time something changes: a new model, a new prompt, a new tool. The result tells you whether the change helped, hurt, or did nothing you can measure.

## The loop

1. **Tasks.** Each task is an input and a known right answer (or a rule for judging one). Here: a pay stub and "what was the gross pay for this period?"
2. **Run.** The model answers every task.
3. **Grade.** Prefer the cheapest, most deterministic grader that works:
   - **Exact match** for facts with one right answer (a number, a date, a name).
   - **Rubric** for answers with several yes/no parts ("names the missing document", "does not invent one").
   - **AI grader** only where judgment is unavoidable (is this explanation specific and fair?).
4. **Compare.** Put two runs side by side and look at which tasks flipped.
5. **Decide.** The report says "looks better", "looks worse" or "no clear difference", and suggests what to do.

## How to read the report

- **Pass rate.** The share of tasks answered completely right. One wrong field fails the task.
- **The range under it.** The true pass rate is probably somewhere in that band. With 60 tasks the band is about 20 points wide, so a 3 point move means nothing.
- **Fixed and regressed.** Tasks that went wrong to right, and right to wrong. Look at regressions first. They are the cost of the change.
- **Chance this gap is luck.** If it is high, the difference could be noise. Do not ship on it.
- **Heatmap.** Rows that mix green and red tell the runs apart. All-green or all-red rows are dead weight.
- **Dev and test.** Tune prompts on dev tasks only. Test tasks are held back to show whether you only improved on tasks you stared at.

## Three habits worth keeping

1. **Write tasks that discriminate.** If every model passes, the task measures nothing.
2. **Reward saying "not present".** A model that invents a missing field is worse than one that says it is not there.
3. **Check the AI grader against a human.** `evalpond calibrate` has you label about 20 answers and shows how often the AI grader agrees.

This tool is for learning how this works. It is a small harness, not a production eval platform.
