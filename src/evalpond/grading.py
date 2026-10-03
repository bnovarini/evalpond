"""Dispatch a task's grading specs to the right grader and combine scores."""
from __future__ import annotations

from typing import Any

from .graders.exact import grade_exact
from .schema import GradeResult, ModelOutput, Task

PASS_AT = 0.999


def grade_task(task: Task, out: ModelOutput, judge: Any | None = None) -> tuple[list[GradeResult], float, bool]:
    grades: list[GradeResult] = []
    for spec in task.grading:
        if out.error or out.parsed is None:
            grades.append(GradeResult(method=spec.method, score=0.0, weight=spec.weight,
                                      details={"error": out.error or "could not parse a JSON answer"}))
        elif spec.method == "exact":
            grades.append(grade_exact(spec, task.expected, out.parsed))
        elif spec.method == "rubric":
            from .graders.rubric import grade_rubric
            grades.append(grade_rubric(spec, task, out, judge))
        elif spec.method == "judge":
            from .graders.judge import grade_judge
            grades.append(grade_judge(spec, task, out, judge))
        else:
            raise ValueError(spec.method)
    total_w = sum(g.weight for g in grades) or 1.0
    score = sum(g.score * g.weight for g in grades) / total_w
    return grades, round(score, 4), score >= PASS_AT
