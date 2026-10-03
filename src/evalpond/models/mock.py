"""Deterministic scripted model for CI and demos. No API key, no network.

It answers from the task's expected values, then corrupts some of them. How often is set by
`skill` (0..1). Corruption is seeded by (seed, task id, repeat), so a run is reproducible.
"""
from __future__ import annotations

import hashlib
import json
import random
from typing import Any

from ..schema import DocumentRef, ModelConfig, ModelOutput


def _rng(*parts: object) -> random.Random:
    h = hashlib.sha256("|".join(map(str, parts)).encode()).hexdigest()
    return random.Random(int(h[:16], 16))


def _corrupt(value: Any, rng: random.Random) -> Any:
    if isinstance(value, bool):
        return not value
    if isinstance(value, (int, float)):
        return round(float(value) * rng.choice([0.5, 0.9, 1.1, 2.0, 10.0]) + rng.choice([0, 1, 100]), 2)
    if isinstance(value, str):
        if len(value) == 10 and value[4] == "-" and value[7] == "-":  # ISO date
            return value[:8] + f"{rng.randint(1, 28):02d}"
        return rng.choice(["Unknown", value + " Inc", value.split(" ")[0], ""])
    if isinstance(value, list):
        return value[:-1] if value and rng.random() < 0.6 else value + ["extra item"]
    return value


class MockAdapter:
    def __init__(self, cfg: ModelConfig):
        self.name = cfg.name
        self.skill = float(cfg.params.get("skill", 0.8))
        self.seed = cfg.params.get("seed", 0)
        self.cost_per_call = float(cfg.params.get("cost_per_call", 0.0))

    def run(self, prompt: str, document: DocumentRef) -> ModelOutput:
        if not document.oracle:
            return ModelOutput(text="{}", parsed={}, error="mock adapter needs an oracle")
        rng = _rng(self.name, self.seed, document.task_id, document.repeat)
        answer: dict[str, Any] = dict(document.oracle)
        if rng.random() >= self.skill:
            # a miss: corrupt one or two fields (never the whole answer), like a real near-miss
            keys = [k for k in answer if k != "explanation"]
            for k in rng.sample(keys, k=min(len(keys), rng.choice([1, 1, 2]))):
                v = answer[k]
                answer[k] = ("Unknown Corp" if rng.random() < 0.5 else "N/A") if v is None else _corrupt(v, rng)
            if "explanation" in answer and rng.random() < 0.5:
                answer["explanation"] = "Everything looks fine."
        text = json.dumps(answer)
        return ModelOutput(
            text=text,
            parsed=answer,
            latency_s=round(0.2 + rng.random() * 0.4, 3),
            input_tokens=len(prompt) // 4,
            output_tokens=len(text) // 4,
            cost_usd=self.cost_per_call,
            doc_mode="text",
        )
