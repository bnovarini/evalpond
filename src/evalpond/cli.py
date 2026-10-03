"""Command line entry point: evalpond gen | run | report | compare | quickstart | calibrate."""
from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

from . import __version__

BANNER = "All documents are synthetic. Never submit real documents to this tool. (see NOTICE.md)"
DEFAULT_TASKSET = "tasksets/income_v1"


def _csv(s: str | None) -> set[str] | None:
    return {x.strip() for x in s.split(",") if x.strip()} if s else None


def cmd_gen(a: argparse.Namespace) -> int:
    from .generator.taskset import build

    m = build(a.seed, Path(a.out))
    print(f"Generated {m['task_count']} synthetic tasks in {a.out} (seed {a.seed}).")
    print(f"  by category: {m['by_category']}  difficulty: {m['by_difficulty']}  split: {m['by_split']}")
    return 0


def cmd_run(a: argparse.Namespace) -> int:
    from .runner import CostCapExceeded, load_models, run_taskset

    models = load_models(Path(a.models))
    if a.model not in models:
        print(f"Unknown model '{a.model}'. Available: {', '.join(models)}", file=sys.stderr)
        return 2
    judge = None
    if a.judge:
        from .graders.judge import build_judge
        judge = build_judge(load_models(Path(a.models))[a.judge])
    run_id = a.run_id or f"{a.model}-{datetime.now():%Y%m%d-%H%M%S}"
    last = {"n": -1}

    def progress(done: int, total: int) -> None:
        pct = done * 100 // max(total, 1)
        if pct != last["n"] and pct % 10 == 0:
            last["n"] = pct
            print(f"  {done}/{total} answers graded", file=sys.stderr)

    try:
        run = run_taskset(Path(a.taskset), models[a.model], run_id=run_id, out_dir=Path(a.out),
                          repeats=a.repeats, categories=_csv(a.categories), splits=_csv(a.split),
                          concurrency=a.concurrency, cost_cap=a.cost_cap, judge=judge, progress=progress)
    except CostCapExceeded as e:
        print(f"Stopped: {e}", file=sys.stderr)
        return 3
    n = len(run.results)
    passed = sum(r.passed for r in run.results)
    print(f"Run {run.run_id}: {passed}/{n} answers fully correct ({passed * 100 // max(n, 1)}%). Saved to {a.out}/{run.run_id}.json")
    return 0


def cmd_todo(a: argparse.Namespace) -> int:
    print(f"evalpond {a.cmd}: not implemented yet", file=sys.stderr)
    return 2


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="evalpond", description=__doc__)
    p.add_argument("--version", action="version", version=f"evalpond {__version__}")
    sub = p.add_subparsers(dest="cmd")
    g = sub.add_parser("gen", help="generate the synthetic task set (seeded)")
    g.add_argument("--seed", type=int, default=42)
    g.add_argument("--out", default=DEFAULT_TASKSET)
    g.set_defaults(fn=cmd_gen)
    r = sub.add_parser("run", help="run a model over a task set")
    r.add_argument("--model", required=True, help="model name from models.yaml")
    r.add_argument("--models", default="models.yaml")
    r.add_argument("--taskset", default=DEFAULT_TASKSET)
    r.add_argument("--out", default="runs")
    r.add_argument("--run-id")
    r.add_argument("--repeats", type=int, default=1)
    r.add_argument("--categories", help="e.g. A,B")
    r.add_argument("--split", help="dev, test, or dev,test (default: both)")
    r.add_argument("--concurrency", type=int, default=4)
    r.add_argument("--cost-cap", type=float, help="abort when estimated spend passes this many USD")
    r.add_argument("--judge", help="model name from models.yaml to use as the AI grader")
    r.set_defaults(fn=cmd_run)
    for name, help_ in [("report", "build the static HTML report"), ("compare", "compare two runs in the terminal"),
                        ("quickstart", "10-minute guided first run, no API keys"),
                        ("calibrate", "hand-label answers to measure the AI grader")]:
        sub.add_parser(name, help=help_).set_defaults(fn=cmd_todo)
    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "cmd", None):
        parser.print_help()
        return 0
    print(BANNER, file=sys.stderr)
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
