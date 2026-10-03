"""Fails the build if the repo or a generated task set contains flagged vendor or employer terms."""
import hashlib
import re
from pathlib import Path

from evalpond.generator.taskset import build

ROOT = Path(__file__).resolve().parents[1]
SKIP_DIRS = {".git", ".venv", "__pycache__", ".pytest_cache", ".ruff_cache", "tasksets", "runs", "site", "dist"}
SKIP_FILES = {"denylist.txt", "denylist.sha256", "uv.lock"}
TEXT_SUFFIXES = {".py", ".md", ".txt", ".yaml", ".yml", ".toml", ".json", ".jsonl", ".js", ".css", ".html"}


def _lists():
    plain = {w.strip() for w in (ROOT / "denylist.txt").read_text().splitlines() if w.strip() and not w.startswith("#")}
    hashed = {w.strip() for w in (ROOT / "denylist.sha256").read_text().splitlines() if w.strip() and not w.startswith("#")}
    return plain, hashed


def _scan(path: Path, plain, hashed):
    hits = []
    for tok in set(re.findall(r"[a-z0-9]+", path.read_text(errors="ignore").lower())):
        if tok in plain or hashlib.sha256(tok.encode()).hexdigest() in hashed:
            hits.append(tok if tok in plain else "<hashed term>")
    return hits


def _files(base: Path):
    for p in base.rglob("*"):
        if p.is_file() and not (set(p.relative_to(base).parts) & SKIP_DIRS) and p.name not in SKIP_FILES and p.suffix in TEXT_SUFFIXES:
            yield p


def test_repo_has_no_flagged_terms():
    plain, hashed = _lists()
    bad = {str(p.relative_to(ROOT)): h for p in _files(ROOT) if (h := _scan(p, plain, hashed))}
    assert not bad, bad


def test_generated_task_set_has_no_flagged_terms(tmp_path):
    plain, hashed = _lists()
    build(42, tmp_path / "ts")
    from evalpond.generator.prd import build as build_prd
    build_prd(42, tmp_path / "prd")
    bad = {p.name: h for p in tmp_path.rglob("*") if p.is_file() and p.suffix != ".pdf" and (h := _scan(p, plain, hashed))}
    assert not bad, bad


def test_denylist_actually_catches():
    plain, hashed = _lists()
    sample = ROOT / "tests" / "_probe.txt"
    sample.write_text("payroll by " + "pay" + "chex" + " and an ordinary sentence")
    try:
        assert _scan(sample, plain, hashed) == ["pay" + "chex"]
        sample.write_text("clu" + "tch")
        assert _scan(sample, plain, hashed) == ["<hashed term>"]
    finally:
        sample.unlink()
