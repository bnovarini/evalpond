# Choosing a check

A good task tells a right answer from a wrong one without a person reading it.

## exact (`--exact fields`)
Compares named fields of the model's JSON answer to `--expected` after tidying numbers, dates and names. Best for decisions, numbers, labels, yes/no. `null` means "the input does not say"; the model passes by answering null or "not stated", and fails by inventing a value.

## rubric (`--check "id|plain text|check"`)
Several yes/no criteria, each with a weight of 1. A task passes only if all are met. Checks:

- `mentions:text`: the answer contains the text
- `any_of:a|b|c`: contains at least one
- `none_of:a|b`: contains none (use for forbidden claims, blame, promises)
- `max_words:N`: at most N words
- `field_equals:key=value`: a key in the JSON answer equals the value
- no check at all: an AI grader answers it (needs `--judge`)

Matching is case-insensitive and literal, so list the common spellings in `any_of`.

## judge (`--judge-question`)
An AI grader answers one question about the answer. Use only for tone, helpfulness or similar. It must be a different model from the one under test. Hand-label about 20 answers with `evalpond calibrate` before believing it.

## Sizing
Under 20 tasks only finds problems. 30 or more per failure mode starts to separate models. Keep 10 to 15 percent "the input is silent" tasks and 20 percent `split=test`.
