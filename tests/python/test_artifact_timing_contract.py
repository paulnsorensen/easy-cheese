"""Every human-readable workflow artifact carries timing provenance."""

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_CONTRACTS = (
    "skills/affinage/SKILL.md",
    "skills/age/SKILL.md",
    "skills/briesearch/references/synthesis.md",
    "skills/cook/references/package-report.md",
    "skills/cure/SKILL.md",
    "skills/cut/SKILL.md",
    "skills/hard-cheese/SKILL.md",
    "skills/mold/SKILL.md",
    "skills/pasteurize/SKILL.md",
    "skills/plate/references/durable-writes.md",
    "skills/press/SKILL.md",
    "skills/wheypoint/SKILL.md",
)
TIMING_TEMPLATES = (
    "skills/affinage/references/report-template.md",
    "skills/age/references/report-example.md",
    "skills/briesearch/references/synthesis.md",
    "skills/cook/references/package-report.md",
    "skills/mold/references/mini-spec-mode.md",
)
PR_URL = "https://github.com/paulnsorensen/easy-cheese/pull/126"


def test_every_artifact_contract_links_the_shared_timing_contract() -> None:
    missing = [
        path
        for path in ARTIFACT_CONTRACTS
        if "artifact-timing.md" not in (REPO_ROOT / path).read_text(encoding="utf-8")
    ]

    assert missing == []


def test_every_artifact_template_contains_the_timing_section() -> None:
    missing = [
        path
        for path in TIMING_TEMPLATES
        if "## Timing" not in (REPO_ROOT / path).read_text(encoding="utf-8")
    ]

    assert missing == []


def test_shared_timing_contract_links_the_prototype_pr() -> None:
    contract = REPO_ROOT / "skills" / "cheese" / "references" / "artifact-timing.md"

    assert PR_URL in contract.read_text(encoding="utf-8")
