# Developing

```bash
uv sync --extra dev
uv run pytest -q
uv run ruff check .
```

## Layout

- `src/evalpond/generator/`: seeded synthetic documents (`paystub.py`, `bank_statement.py`, `inconsistencies.py`, `render.py`) and the task set builder (`taskset.py`).
- `src/evalpond/graders/`: `exact.py`, `rubric.py`, `judge.py`, `normalize.py`.
- `src/evalpond/models/`: adapter protocol, `mock.py` (no key needed), `cloud.py` (Anthropic, OpenAI, OpenAI-compatible).
- `src/evalpond/runner.py`: runs a task set, saves one JSON file per run, resumes partial runs, enforces a cost cap.
- `src/evalpond/stats.py`: intervals, paired comparison, agreement.
- `src/evalpond/report/`: builds one static HTML file. `copy.py` holds all reader-facing text.

## Rules that tests enforce

- The same seed gives a byte-identical task set.
- Every generated document is watermarked, in the PDF metadata and the text layer.
- The repo contains no flagged vendor or employer terms (`tests/test_denylist.py`).
- Plain-language report copy contains no statistics jargon outside the "Details for the curious" folds.
- Real adapters never see a task's expected answer.

## Real models

Set `model` and `api_key_env` for an entry in `models.yaml`, export the key, then `uv run evalpond run --model NAME --cost-cap 2`. Add `price_in` / `price_out` (USD per million tokens) to `params` for cost estimates. Model ids and prices change, so none are hard-coded.
