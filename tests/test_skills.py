import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SKILLS = sorted((ROOT / "skills").glob("*/SKILL.md"))


def test_four_skills_with_valid_frontmatter():
    assert [p.parent.name for p in SKILLS] == ["evalpond-audit-run", "evalpond-run-and-explain", "evalpond-start", "evalpond-write-tasks"]
    for p in SKILLS:
        m = re.match(r"---\nname: (.+)\ndescription: >\n((?:  .+\n)+)---\n", p.read_text())
        assert m, p
        assert m.group(1) == p.parent.name
        assert len(" ".join(m.group(2).split())) < 1024


def test_skills_only_use_real_cli_commands():
    from evalpond.cli import build_parser
    subs = set(re.findall(r"^    ([a-z][a-z-]+)\s", build_parser().format_help().split("positional arguments:")[0] + build_parser().format_help().split("positional arguments:")[1], re.MULTILINE)) | {"validate", "add-task", "explain"}
    for p in SKILLS:
        for cmd in re.findall(r"(?:`|^)evalpond ([a-z][a-z-]+)", p.read_text(), re.MULTILINE):
            assert cmd in subs, (p.name, cmd)


def test_run_skill_keeps_keys_out_of_chat_and_cap_on():
    t = (ROOT / "skills" / "evalpond-run-and-explain" / "SKILL.md").read_text()
    assert "Do not ask them to paste it into chat" in t and "--cost-cap" in t


@pytest.mark.parametrize("name", ["plugin.json", "marketplace.json"])
def test_plugin_files(name):
    d = json.loads((ROOT / ".claude-plugin" / name).read_text())
    assert d["name"] == "evalpond"
    if name == "marketplace.json":
        assert d["plugins"][0]["source"] == "./"


def test_credit_in_notice():
    t = (ROOT / "NOTICE.md").read_text()
    assert "ai-evals-course/evals-skills" in t and "Apache" in t
