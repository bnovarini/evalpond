"""Command line entry point: evalpond gen | run | report | compare | quickstart | calibrate."""
from __future__ import annotations

import argparse
import sys

from . import __version__

BANNER = "All documents are synthetic. Never submit real documents to this tool. (see NOTICE.md)"


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="evalpond", description=__doc__)
    p.add_argument("--version", action="version", version=f"evalpond {__version__}")
    sub = p.add_subparsers(dest="cmd")
    sub.add_parser("gen", help="generate the synthetic task set (seeded)")
    sub.add_parser("run", help="run a model over a task set")
    sub.add_parser("report", help="build the static HTML report")
    sub.add_parser("compare", help="compare two runs in the terminal")
    sub.add_parser("quickstart", help="10-minute guided first run, no API keys")
    sub.add_parser("calibrate", help="hand-label answers to measure the AI grader")
    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not args.cmd:
        parser.print_help()
        return 0
    print(BANNER, file=sys.stderr)
    print(f"evalpond {args.cmd}: not implemented yet", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
