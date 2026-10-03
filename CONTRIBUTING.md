# Contributing

Small, readable changes are welcome.

## Ground rules

1. **Synthetic only.** Never add real documents, real names, real account numbers or real borrower data, even redacted.
2. **No real vendor material.** Layouts are invented. Do not copy any employer, lender, bank or payroll provider's format, field names, logos or terminology. `tests/test_denylist.py` guards this.
3. **Tool, not a course.** No tutorial pages, lessons, quizzes or glossary sites. Teaching lives in the report and in `docs/GUIDE.md`.
4. **Keep the report plain.** New statistics get a one-line plain explanation next to them. Jargon goes in the "Details for the curious" fold.

## Before you open a pull request

```bash
uv run ruff check . && uv run pytest -q
```
