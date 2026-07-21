"""Contract tests for agent-dispatch resolution across workflow skills."""

from __future__ import annotations

from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
SKILLS = REPO_ROOT / "skills"
DISPATCHING = {
    "affinage",
    "age",
    "briesearch",
    "cook",
    "cure",
    "hard-cheese",
    "mold",
    "ultracook",
    "wheypoint",
}
TABLE_COLUMNS = (
    "Work",
    "Preferred types",
    "Permissions/isolation",
    "Minimum power",
    "Effort",
    "Fallback",
)
POWER = {"cheap", "default", "powerful"}
EFFORT = {"low", "medium", "high"}


def _body(name: str) -> str:
    return (SKILLS / name / "SKILL.md").read_text(encoding="utf-8")


def _frontmatter(body: str) -> dict:
    _, raw, _ = body.split("---", 2)
    return yaml.safe_load(raw)


def _dispatching_skills() -> set[str]:
    marked = set()
    for path in SKILLS.glob("*/SKILL.md"):
        metadata = _frontmatter(path.read_text(encoding="utf-8")).get("metadata", {})
        if metadata.get("dispatches-agents") is True:
            marked.add(path.parent.name)
    return marked


def _agent_resolution_rows(body: str) -> list[list[str]]:
    section = body.split("## Agent resolution", 1)[1]
    lines = section.splitlines()
    table_start = next(i for i, line in enumerate(lines) if line.startswith("| Work |"))
    rows = []
    for line in lines[table_start + 2 :]:
        if not line.startswith("|"):
            break
        rows.append([cell.strip().strip("`") for cell in line.strip("|").split("|")])
    return rows


def test_exact_dispatching_skill_set_is_marked() -> None:
    assert _dispatching_skills() == DISPATCHING


def test_shared_reference_is_normative_and_linked() -> None:
    reference = SKILLS / "cheese" / "references" / "agent-resolution.md"
    assert reference.is_file()
    text = reference.read_text(encoding="utf-8")
    for term in (
        "capabilities",
        "minimum power",
        "exact easy-cheese specialist",
        "compatible specialist",
        "general",
        "unknown power",
        "prompt-only",
        "agent_resolution",
    ):
        assert term in text.lower()

    assert "agent-resolution.md" in (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    assert "agent-resolution.md" in (
        SKILLS / "cheese" / "references" / "harness-portability.md"
    ).read_text(encoding="utf-8")


def test_each_dispatching_skill_has_local_resolution_contract() -> None:
    for name in DISPATCHING:
        body = _body(name)
        assert "## Agent resolution" in body, name
        assert "../cheese/references/agent-resolution.md" in body, name
        assert "agent_resolution" in body, name

        section = body.split("## Agent resolution", 1)[1]
        header = next(line for line in section.splitlines() if line.startswith("| Work |"))
        assert tuple(cell.strip() for cell in header.strip("|").split("|")) == TABLE_COLUMNS

        rows = _agent_resolution_rows(body)
        assert rows, name
        assert all(len(row) == len(TABLE_COLUMNS) for row in rows), name
        assert all(row[3] in POWER for row in rows), name
        assert all(row[4] in EFFORT for row in rows), name
        assert all(row[0] and row[1] and row[2] and row[5] for row in rows), name
