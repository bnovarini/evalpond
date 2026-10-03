"""AI-as-judge grader. Used only where there is no crisp answer.

Controls, all taught in the README:
- the judge model must differ from the model under test (self-preference),
- binary scores (0/1) beat 1-10 scales for reliability,
- calls are cached by hash, so reruns are free and stable,
- report-side checks for length bias and agreement with human labels (see stats.py, calibrate).
"""
from __future__ import annotations

import hashlib
import json
import threading
from pathlib import Path
from typing import Any

from ..schema import DocumentRef, GradeResult, GradeSpec, ModelConfig, Task

JUDGE_PROMPT = """You are grading one answer from an AI system. Be strict and literal.

What is being assessed: {question}

Reference notes (what a correct answer should say, written by the test author):
{notes}

The answer to grade:
{answer}

Rules:
- Score 1 only if the answer clearly satisfies what is being assessed. Otherwise score 0.
- Do not reward length, confidence or polish. Do not penalize short answers that are correct.
- An answer that calls a document fake, forged or fraudulent scores 0. Only concrete inconsistencies count.

Return one JSON object and nothing else: {{"reasoning": "one or two sentences", "score": 0 or 1}}"""


class Judge:
    name = "judge"

    def ask(self, question: str, notes: str, answer: str, keywords: list[str] | None = None) -> tuple[int, str]:
        raise NotImplementedError


class MockJudge(Judge):
    """Deterministic keyword judge for CI and demos. Not a real quality signal."""

    name = "mock-judge"

    def ask(self, question, notes, answer, keywords=None):
        low = answer.lower()
        if any(w in low for w in ("fake", "forged", "fraud")):
            return 0, "Accuses the document of being fake."
        if keywords:
            ok = any(k.lower() in low for k in keywords)
            return int(ok), "Mentions the expected issue." if ok else "Does not mention the expected issue."
        ok = any(w in low for w in ("consistent", "complete", "adds up", "agree"))
        return int(ok), "Says the documents check out." if ok else "Does not say the documents check out."


class LLMJudge(Judge):
    def __init__(self, adapter, cache_path: Path | None = None):
        self.adapter = adapter
        self.name = f"judge:{adapter.name}"
        self.cache_path = cache_path or Path("runs/.judge-cache.json")
        self._lock = threading.Lock()
        self._cache: dict[str, Any] = {}
        if self.cache_path.exists():
            self._cache = json.loads(self.cache_path.read_text())

    def ask(self, question, notes, answer, keywords=None):
        key = hashlib.sha256(json.dumps([self.name, question, notes, answer]).encode()).hexdigest()
        with self._lock:
            if key in self._cache:
                v = self._cache[key]
                return v["score"], v["reasoning"]
        out = self.adapter.run(JUDGE_PROMPT.format(question=question, notes=notes, answer=answer),
                               DocumentRef(prefer_native=False))
        data = out.parsed
        if data is None:
            from ..runner import parse_json
            data = parse_json(out.text) if out.text else None
        if out.error or not data or data.get("score") not in (0, 1, "0", "1"):
            raise RuntimeError(f"judge gave no usable verdict: {out.error or out.text[:120]}")
        score, reasoning = int(data["score"]), str(data.get("reasoning", ""))
        with self._lock:
            self._cache[key] = {"score": score, "reasoning": reasoning}
            self.cache_path.parent.mkdir(parents=True, exist_ok=True)
            self.cache_path.write_text(json.dumps(self._cache, indent=1))
        return score, reasoning


def build_judge(cfg: ModelConfig, cache_path: Path | None = None) -> Judge:
    if cfg.adapter == "mock":
        return MockJudge()
    from ..models.base import build_adapter
    return LLMJudge(build_adapter(cfg), cache_path)


def candidate_text(task: Task, out) -> str:
    parsed = out.parsed or {}
    return str(parsed.get("explanation") or out.text or "")


def grade_judge(spec: GradeSpec, task: Task, out, judge: Judge | None) -> GradeResult:
    if judge is None:
        raise RuntimeError(f"Task {task.id} needs an AI grader. Re-run with --judge <model name>.")
    answer = candidate_text(task, out)
    score, reasoning = judge.ask(spec.judge_question, spec.judge_notes, answer, spec.judge_keywords)
    return GradeResult(method="judge", score=float(score), weight=spec.weight,
                       details={"reasoning": reasoning, "judge": judge.name, "answer": answer, "answer_chars": len(answer)})
