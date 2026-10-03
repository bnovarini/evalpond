"""Core data types: tasks, model outputs, grades, runs."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

Method = Literal["exact", "rubric", "judge"]
Difficulty = Literal["easy", "medium", "hard"]
Split = Literal["dev", "test"]


class RubricItem(BaseModel):
    """One yes/no criterion. `check` names a programmatic check; if empty, the judge answers it."""

    id: str
    text: str
    weight: float = 1.0
    check: str = ""  # e.g. "mentions:second stub", "field_equals:complete=false"


class GradeSpec(BaseModel):
    method: Method
    weight: float = 1.0
    fields: list[str] = Field(default_factory=list)  # exact: fields to compare
    normalize: str = "money_date_name"
    rubric: list[RubricItem] = Field(default_factory=list)  # rubric method
    judge_question: str = ""  # judge method: what the judge assesses
    judge_notes: str = ""  # ground-truth notes shown to the judge only


class Task(BaseModel):
    id: str
    category: str  # A..E, see tasksets/income_v1/manifest.yaml
    difficulty: Difficulty
    split: Split = "dev"
    documents: list[str] = Field(default_factory=list)  # PDF paths, relative to the task set
    text_documents: list[str] = Field(default_factory=list)  # OCR-style text fallbacks
    prompt_template: str
    expected: dict[str, Any]
    grading: list[GradeSpec]
    tags: list[str] = Field(default_factory=list)
    plain_title: str = ""
    why_it_matters: str = ""
    what_good_looks_like: str = ""


class DocumentRef(BaseModel):
    """What an adapter receives. It may send the PDFs natively or fall back to text."""

    pdf_paths: list[str] = Field(default_factory=list)
    text: str = ""  # concatenated text fallback
    prefer_native: bool = True
    task_id: str = ""
    repeat: int = 0
    # Only the mock adapter reads this (so CI can run with no API key). Real adapters ignore it.
    oracle: dict[str, Any] | None = None


class ModelOutput(BaseModel):
    text: str = ""
    parsed: dict[str, Any] | None = None
    latency_s: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    raw: Any = None
    error: str | None = None
    doc_mode: Literal["native", "text"] = "text"


class GradeResult(BaseModel):
    method: Method
    score: float  # 0..1
    weight: float = 1.0
    details: dict[str, Any] = Field(default_factory=dict)


class TaskResult(BaseModel):
    task_id: str
    repeat: int = 0
    output: ModelOutput
    grades: list[GradeResult] = Field(default_factory=list)
    score: float = 0.0  # weighted mean of grades
    passed: bool = False  # score >= pass threshold (default 1.0 for exact-only, see runner)


class ModelConfig(BaseModel):
    name: str
    adapter: str
    model: str = ""
    params: dict[str, Any] = Field(default_factory=dict)
    api_key_env: str = ""


class Run(BaseModel):
    run_id: str
    label: str = ""
    model: ModelConfig
    prompt_hashes: dict[str, str] = Field(default_factory=dict)
    taskset: str
    taskset_version: str = ""
    judge_model: str = ""
    git_sha: str = ""
    started_at: str = ""
    finished_at: str = ""
    repeats: int = 1
    total_cost_usd: float = 0.0
    results: list[TaskResult] = Field(default_factory=list)
