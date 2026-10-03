# Writing your own tasks

The harness does not care about income documents. Any task set in this format works. A task set is a folder with `tasks.jsonl`, a `manifest.yaml`, and the documents.

## One task, one JSON line

```json
{"id": "stub-017", "category": "A", "difficulty": "medium", "split": "dev",
 "documents": ["docs/stub-017-1.pdf"], "text_documents": ["docs/stub-017-1.txt"],
 "prompt_template": "extract_stub_v1",
 "expected": {"employer": "Harbor Lane Logistics", "gross_pay": 2314.5},
 "grading": [{"method": "exact", "fields": ["employer", "gross_pay"]}],
 "plain_title": "Read the key fields from a pay stub",
 "why_it_matters": "One sentence a non-engineer understands.",
 "what_good_looks_like": "What a right answer contains."}
```

- `documents` are sent natively when you pass `--native`. Otherwise the `text_documents` are pasted into the prompt, so text-only models still run.
- `expected` holds the right answer. A value of `null` means "the document does not say". Answering `null` or "N/A" is right, and inventing a value is wrong.
- `grading` is a list. Methods: `exact` (fields compared after normalizing money, dates and names), `rubric` (weighted yes/no criteria), `judge` (an AI grader reads the answer).
- Prompts live in `src/evalpond/prompts/`, versioned by name, so a prompt change is a separate variable from a task change.
- `plain_title`, `why_it_matters` and `what_good_looks_like` are shown in the report. Write them for a reader who does not code.

## What makes a good task

1. **It discriminates.** Aim for a spread: a strong model near 80-90%, a weak one near 40-60%. A task everyone passes or everyone fails measures nothing. The heatmap shows which are dead weight.
2. **One idea per task.** When it fails, you should know why.
3. **Include "not present" cases** (about 10-15%).
4. **Keep a held-out test split** (about 20%) and do not tune on it.
5. **Prefer exact grading.** Use a rubric when there are several parts, and an AI grader only when you must.
