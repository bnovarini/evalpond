"""Command line entry point: evalpond gen | run | report | compare | quickstart | calibrate | validate | add-task | explain."""
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
    if a.pack == "prd":
        from .generator.prd import build
        out = a.out or "tasksets/prd_v1"
    else:
        from .generator.taskset import build
        out = a.out or DEFAULT_TASKSET
    a.out = out
    m = build(a.seed, Path(out))
    print(f"Generated {m['task_count']} synthetic tasks in {a.out} (seed {a.seed}).")
    print(f"  by category: {m['by_category']}  difficulty: {m['by_difficulty']}  split: {m['by_split']}")
    return 0


DEFAULT_COST_CAP = 2.0


def cmd_run(a: argparse.Namespace) -> int:
    from .runner import CostCapExceeded, load_models, run_taskset

    models = load_models(Path(a.models))
    if a.model not in models:
        print(f"Unknown model '{a.model}'. Available: {', '.join(models)}", file=sys.stderr)
        return 2
    cfg = models[a.model]
    if cfg.adapter != "mock":
        # A cost cap only works if spend can be estimated, so a real model needs prices in models.yaml.
        if not (float(cfg.params.get("price_in", 0)) or float(cfg.params.get("price_out", 0))):
            print(f"'{a.model}' has no price_in / price_out in models.yaml, so the cost cap cannot work. "
                  "Add the provider's current prices (USD per million tokens) under params, then run again.", file=sys.stderr)
            return 2
        if a.cost_cap is None and not a.no_cost_cap:
            a.cost_cap = DEFAULT_COST_CAP
            print(f"Cost cap: ${DEFAULT_COST_CAP:.2f} (default for real models; pass --cost-cap N to change it).", file=sys.stderr)
    judge = None
    if a.judge:
        from .graders.judge import build_judge
        jcfg = load_models(Path(a.models))[a.judge]
        if jcfg.name == a.model or (jcfg.model and jcfg.model == models[a.model].model):
            print("The AI grader must be a different model from the one under test (models grade their own answers too kindly).", file=sys.stderr)
            return 2
        judge = build_judge(jcfg, Path(a.out) / ".judge-cache.json")
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
                          concurrency=a.concurrency, cost_cap=a.cost_cap, judge=judge, native=a.native, progress=progress)
    except CostCapExceeded as e:
        print(f"Stopped: {e}", file=sys.stderr)
        return 3
    n = len(run.results)
    passed = sum(r.passed for r in run.results)
    print(f"Run {run.run_id}: {passed}/{n} answers fully correct ({passed * 100 // max(n, 1)}%). Saved to {a.out}/{run.run_id}.json")
    return 0


def cmd_calibrate(a: argparse.Namespace) -> int:
    import json

    from .calibrate import run_calibration
    from .schema import Run

    run = Run(**json.loads(Path(a.run).read_text()))
    run_calibration(run, Path(a.taskset), Path(a.labels), n=a.n)
    return 0


def cmd_compare(a: argparse.Namespace) -> int:
    import json

    from .schema import Run
    from .stats import compare_runs

    ra, rb = (Run(**json.loads(Path(p).read_text())) for p in (a.run_a, a.run_b))
    c = compare_runs(ra, rb)
    print(f"{ra.label or ra.run_id} ({c.pass_a * 100:.0f}% fully correct)  ->  {rb.label or rb.run_id} ({c.pass_b * 100:.0f}%)")
    print(f"+{len(c.fixed)} fixed, -{len(c.regressed)} regressed, {c.unchanged_pass} still right, {c.unchanged_fail} still wrong")
    print(f"Verdict: {c.verdict} (chance this gap is luck: {c.p_value * 100:.0f}%)")
    for n in c.notes:
        print(n)
    return 0


def cmd_report(a: argparse.Namespace) -> int:
    from .report.build import build_report

    labels = Path(a.labels) if Path(a.labels).exists() else None
    path = build_report(Path(a.runs), Path(a.taskset), Path(a.out), labels, a.title)
    print(f"Report written to {path}. Open it in a browser.")
    return 0


def cmd_quickstart(a: argparse.Namespace) -> int:
    """Clean clone to an open report, no API keys. Prints each step in plain language."""
    import webbrowser

    from .generator.taskset import build
    from .graders.judge import build_judge
    from .report.build import build_report
    from .runner import load_models, run_taskset

    taskset, runs = Path(DEFAULT_TASKSET), Path(a.runs)
    models = load_models(Path("models.yaml"))
    print("\nStep 1 of 4: make the test. We generate 60 fake income documents (pay stubs and bank statements)")
    print("with known right answers. Everything is synthetic, so nothing real is involved.")
    m = build(42, taskset)
    print(f"  Done: {m['task_count']} tasks. Each one has a document, a question, and the correct answer.\n")
    judge = build_judge(models["mock-judge"])
    steps = [("mock-weak", "a weak stand-in model"), ("mock-strong", "a stronger stand-in model"),
             ("mock-strong-b", "a near-identical twin of the strong one")]
    print("Step 2 of 4: take the test. Three scripted stand-in models answer every task. They are fake on")
    print("purpose, so this works with no API key and no cost. With real models you would see real mistakes.")
    for i, (name, blurb) in enumerate(steps, 1):
        run = run_taskset(taskset, models[name], run_id=name, out_dir=runs, judge=judge, resume=False)
        ok = sum(r.passed for r in run.results)
        print(f"  {name} ({blurb}): {ok} of {len(run.results)} answers completely right")
    print("\nStep 3 of 4: grade the answers. Most are checked by exact match against the known answer. A few")
    print("need judgment, so a second AI grades those (here a simple scripted one).\n")
    print("Step 4 of 4: read the results. Building the report...")
    path = build_report(runs, taskset, Path(a.out), None, "evalpond quickstart")
    print(f"  Report: {path}")
    print("\nWhat to look at first:")
    print("  1. Compare runs: mock-weak vs mock-strong. The verdict says 'looks better' and tells you why.")
    print("  2. Compare mock-strong vs mock-strong-b. Nearly identical, so it says 'no clear difference'.")
    print("     That is the lesson: small gaps on 60 tasks are noise.")
    print("  3. Heatmap: rows that mix green and red are the tasks that tell the runs apart.")
    if not a.no_open:
        webbrowser.open(path.resolve().as_uri())
    return 0


def cmd_validate(a: argparse.Namespace) -> int:
    import json

    from .taskkit import render_validation, validate_taskset

    rep = validate_taskset(Path(a.taskset))
    print(json.dumps(rep, indent=1) if a.json else render_validation(rep))
    return 0 if rep["ok"] else 1


def _task_spec(a: argparse.Namespace) -> tuple[dict, list[str]]:
    import json

    from .schema import GradeSpec
    from .taskkit import rubric_from_flags

    if a.from_json:
        spec = json.loads(Path(a.from_json).read_text())
        return spec, spec.pop("inputs", [])
    inputs = list(a.input or []) + [Path(p).read_text() for p in (a.input_file or [])]
    expected = json.loads(Path(a.expected_file).read_text() if a.expected_file else (a.expected or "{}"))
    grading = []
    if a.exact:
        grading.append(GradeSpec(method="exact", fields=_csv_list(a.exact)).model_dump())
    if a.check:
        grading.append(GradeSpec(method="rubric", rubric=rubric_from_flags(a.check)).model_dump())
    if a.judge_question:
        grading.append(GradeSpec(method="judge", judge_question=a.judge_question, judge_notes=a.judge_notes or "").model_dump())
    spec = {"id": a.id, "failure_mode": a.failure_mode, "category": a.category, "difficulty": a.difficulty,
            "split": a.split, "plain_title": a.title, "why_it_matters": a.why, "what_good_looks_like": a.good,
            "question": a.question, "prompt_template": a.prompt_template, "expected": expected, "grading": grading,
            "tags": list(a.tag or []) + ([f"sev:{a.severity}"] if a.severity else [])}
    return {k: v for k, v in spec.items() if v not in (None, "")}, inputs


def _csv_list(s: str) -> list[str]:
    return [x.strip() for x in s.split(",") if x.strip()]


def cmd_add_task(a: argparse.Namespace) -> int:
    import json

    from .taskkit import add_task

    try:
        spec, inputs = _task_spec(a)
        res = add_task(Path(a.taskset), spec, inputs, dry_run=a.dry_run)
    except (ValueError, OSError) as e:
        print(f"Could not read the task: {e}", file=sys.stderr)
        return 2
    if a.json:
        print(json.dumps(res, indent=1, default=str))
    else:
        for i in res["errors"]:
            print(f"ERROR   {i['message']}")
        for i in res["warnings"]:
            print(f"warning {i['message']}")
        if res["ok"]:
            print(f"{'Checked (not written)' if a.dry_run else 'Added'} task {res['id']}." + ("" if a.dry_run else f" Next: evalpond validate {a.taskset}"))
        else:
            print(f"Task {res['id']} was not added.")
    return 0 if res["ok"] else 1


def cmd_explain(a: argparse.Namespace) -> int:
    import json

    from .explain import explain_run, render_explanation
    from .schema import Run

    run = Run(**json.loads(Path(a.run).read_text()))
    ts = Path(a.taskset) if a.taskset else Path("tasksets") / run.taskset
    e = explain_run(run, ts if ts.exists() else None, top=a.top)
    print(json.dumps(e, indent=1, default=str) if a.json else render_explanation(e))
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="evalpond", description=__doc__)
    p.add_argument("--version", action="version", version=f"evalpond {__version__}")
    sub = p.add_subparsers(dest="cmd")
    g = sub.add_parser("gen", help="generate the synthetic task set (seeded)")
    g.add_argument("--seed", type=int, default=42)
    g.add_argument("--out", default=None, help="where to write the task set")
    g.add_argument("--pack", choices=["income", "prd"], default="income", help="income documents (default) or product requirement documents")
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
    r.add_argument("--no-cost-cap", action="store_true", help="real models only: run without the default $2 cap")
    r.add_argument("--native", action="store_true", help="send PDFs to the model (default: send the text layer)")
    r.add_argument("--judge", help="model name from models.yaml to use as the AI grader")
    r.set_defaults(fn=cmd_run)
    c = sub.add_parser("compare", help="compare two runs in the terminal")
    c.add_argument("run_a")
    c.add_argument("run_b")
    c.set_defaults(fn=cmd_compare)
    k = sub.add_parser("calibrate", help="hand-label answers to measure the AI grader")
    k.add_argument("--run", required=True, help="a run JSON that used --judge")
    k.add_argument("--taskset", default=DEFAULT_TASKSET)
    k.add_argument("--labels", default="calibration/labels.jsonl")
    k.add_argument("-n", type=int, default=20)
    k.set_defaults(fn=cmd_calibrate)
    rp = sub.add_parser("report", help="build the static HTML report")
    rp.add_argument("runs", nargs="?", default="runs")
    rp.add_argument("--taskset", default=DEFAULT_TASKSET)
    rp.add_argument("--out", default="site")
    rp.add_argument("--labels", default="calibration/labels.jsonl")
    rp.add_argument("--title", default="evalpond report")
    rp.set_defaults(fn=cmd_report)
    q = sub.add_parser("quickstart", help="10-minute guided first run, no API keys")
    q.add_argument("--runs", default="runs")
    q.add_argument("--out", default="site")
    q.add_argument("--no-open", action="store_true", help="do not open the report in a browser")
    q.set_defaults(fn=cmd_quickstart)
    v = sub.add_parser("validate", help="check a task set: will the harness understand it, can each task fail?")
    v.add_argument("taskset", nargs="?", default=DEFAULT_TASKSET)
    v.add_argument("--json", action="store_true")
    v.set_defaults(fn=cmd_validate)
    t = sub.add_parser("add-task", help="add one task to a task set (checked before it is written)")
    t.add_argument("--taskset", default="tasksets/mine")
    t.add_argument("--from-json", help="a JSON file with the whole task (and an `inputs` list of document texts)")
    t.add_argument("--failure-mode", help="the failure this task probes, in plain words; becomes the report category")
    t.add_argument("--id")
    t.add_argument("--category")
    t.add_argument("--difficulty", choices=["easy", "medium", "hard"])
    t.add_argument("--split", choices=["dev", "test"])
    t.add_argument("--title", help="plain-language title shown in the report")
    t.add_argument("--why", help="why this matters, one sentence")
    t.add_argument("--good", help="what a right answer contains")
    t.add_argument("--question", help="what the model is asked to do with the input")
    t.add_argument("--prompt-template", help="default generic_v1; or a name in <taskset>/prompts/")
    t.add_argument("--input", action="append", help="the document text (repeatable)")
    t.add_argument("--input-file", action="append", help="a text file to use as the document (repeatable)")
    t.add_argument("--expected", help='the right answer as JSON, e.g. \'{"decision": "deny"}\'. Use null for "the input does not say"')
    t.add_argument("--expected-file")
    t.add_argument("--exact", help="comma-separated fields in --expected to compare exactly")
    t.add_argument("--check", action="append", help="rubric criterion 'id|plain text|check'; checks: mentions:, any_of:a|b, none_of:a|b, max_words:N, field_equals:k=v")
    t.add_argument("--judge-question", help="AI-graded: the yes/no question the grader answers")
    t.add_argument("--judge-notes")
    t.add_argument("--severity", choices=["high", "medium", "low"], help="how bad is this failure for users; the explanation fixes high ones first")
    t.add_argument("--tag", action="append")
    t.add_argument("--dry-run", action="store_true", help="check the task without writing anything")
    t.add_argument("--json", action="store_true")
    t.set_defaults(fn=cmd_add_task)
    x = sub.add_parser("explain", help="explain one run in plain language (--json for agents)")
    x.add_argument("run", help="a run JSON from `evalpond run`")
    x.add_argument("--taskset", help="defaults to tasksets/<name the run used>")
    x.add_argument("--top", type=int, default=8, help="how many weakest answers to list")
    x.add_argument("--json", action="store_true")
    x.set_defaults(fn=cmd_explain)
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
