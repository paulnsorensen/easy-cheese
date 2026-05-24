"""SKILL.md frontmatter and structural smoke tests.

Validates that skills/cheese-factory/SKILL.md is YAML-frontmatter-valid,
names the skill correctly, declares MIT license, and that every promised
reference / script file exists.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

FRONTMATTER_RE = re.compile(r"\A---\r?\n(.*?)\r?\n---\s*(\r?\n|\Z)", re.DOTALL)


@pytest.fixture(scope="module")
def skill_body(skill_md_path: Path) -> str:
    return skill_md_path.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def frontmatter(skill_body: str) -> dict:
    match = FRONTMATTER_RE.match(skill_body)
    assert match, "SKILL.md must lead with YAML frontmatter"
    fm = yaml.safe_load(match.group(1))
    assert isinstance(fm, dict), "frontmatter must parse to a mapping"
    return fm


class TestFrontmatter:
    def test_name_matches_directory(self, frontmatter: dict) -> None:
        assert frontmatter["name"] == "cheese-factory"

    def test_description_present_and_non_empty(self, frontmatter: dict) -> None:
        desc = frontmatter.get("description", "")
        assert isinstance(desc, str)
        assert desc.strip(), "description must be non-empty"

    def test_license_is_mit(self, frontmatter: dict) -> None:
        assert frontmatter.get("license") == "MIT"

    def test_only_allowed_keys(self, frontmatter: dict) -> None:
        # Mirror validate_skills.ALLOWED_KEYS.
        allowed = {
            "name",
            "description",
            "license",
            "compatibility",
            "metadata",
            "allowed-tools",
            "version",
            "argument-hint",
            "disable-model-invocation",
            "user-invocable",
            "model",
            "context",
            "agent",
            "hooks",
        }
        extra = set(frontmatter) - allowed
        assert not extra, f"frontmatter has disallowed keys: {sorted(extra)}"

    def test_description_names_orchestrator_role(self, frontmatter: dict) -> None:
        # The description is the trigger; load-bearing phrases must be present.
        desc = frontmatter["description"].lower()
        assert "decompose" in desc or "decomposes" in desc
        assert "5" in desc, "must say '5+' curds — anything fewer routes to /ultracook"
        assert "fromagerie" in desc, "name the bespoke-agent sibling for routing clarity"


class TestBundledFilesExist:
    """Every file the spec promises must be present."""

    REQUIRED_REFERENCES = (
        "decomposer-prompt.md",
        "curd-prompt.md",
        "wiring-prompt.md",
        "pr-planner-prompt.md",
        "manifest-schema.json",
        "pr-plan-schema.json",
        "spawn-primitive-reference.md",
    )

    # manifest_io.py and schema.py live in shared/scripts/ and are bundled into
    # cheese-factory.pyz by scripts/build_pyz.py. See
    # tests/shared/python/test_manifest_io.py for direct coverage.

    REQUIRED_SCRIPTS = (
        "validate_decomposition.py",
        "validate_manifest.py",
        "validate_pr_plan.py",
        "pr_plan_to_branches.py",
    )

    def test_references_present(self, cf_dir: Path) -> None:
        for ref in self.REQUIRED_REFERENCES:
            assert (cf_dir / "references" / ref).is_file(), (
                f"missing required reference: references/{ref}"
            )

    def test_scripts_present(self) -> None:
        src = Path(__file__).resolve().parents[3] / "src" / "cheese-factory"
        for script in self.REQUIRED_SCRIPTS:
            assert (src / script).is_file(), (
                f"missing required script: src/cheese-factory/{script}"
            )

    def test_shared_helpers_present(self) -> None:
        repo_root = Path(__file__).resolve().parents[3]
        for helper in ("manifest_io.py", "schema.py"):
            assert (repo_root / "shared" / "scripts" / helper).is_file(), (
                f"missing required shared helper: shared/scripts/{helper}"
            )

    def test_scripts_executable(self) -> None:
        src = Path(__file__).resolve().parents[3] / "src" / "cheese-factory"
        for script in self.REQUIRED_SCRIPTS:
            mode = (src / script).stat().st_mode
            assert mode & 0o111, f"src/cheese-factory/{script} must be executable"


class TestBodyMentionsLoadBearingContracts:
    """String-shaped checks for contract clauses that downstream tools rely on.

    Same pattern as tests/python/test_ultracook_skills.py — catches silent
    removal of load-bearing phrases without modelling the full SKILL grammar.
    """

    def test_lists_eight_phases(self, skill_body: str) -> None:
        # Spec mandates eight phases (0-7). Anchor on the Phases header.
        assert "## Phases" in skill_body
        for phase_name in (
            "Phase 0 — Pre-compile",
            "Phase 1 — Seed",
            "Phase 2 — Curds",
            "Phase 3 — Merge curds",
            "Phase 4 — Wiring",
            "Phase 5 — Final merge",
            "Phase 6 — Post-merge review",
            "Phase 7 — PR plan",
        ):
            assert phase_name in skill_body, f"missing phase header: {phase_name}"

    def test_five_decomposition_criteria_present(self, skill_body: str) -> None:
        # Each of the five criteria must be named in the body.
        for criterion in (
            "One behaviour per curd",
            "One acceptance criterion",
            "One test target",
            "File-disjoint",
            "Commit-worthy alone",
        ):
            assert criterion in skill_body, f"missing criterion: {criterion}"

    def test_five_spawn_invariants_present(self, skill_body: str) -> None:
        # The five spawn invariants are the harness-agnosticism contract.
        assert "Fresh context per spawn" in skill_body
        assert "Full-peer inheritance" in skill_body
        assert "No chain-forward" in skill_body
        assert "Returns control" in skill_body
        assert "Writes handoff slug" in skill_body

    def test_handoff_slug_schema_fields_present(self, skill_body: str) -> None:
        for field in ("status:", "next:", "artifact:"):
            assert field in skill_body

    def test_pr_layout_shapes_present(self, skill_body: str) -> None:
        for shape in ("single", "orthogonal_flat", "stacked_linear", "diamond_stack"):
            assert shape in skill_body

    def test_hard_propagation_documented(self, skill_body: str) -> None:
        assert "--hard" in skill_body
        assert "/hard-cheese" in skill_body

    def test_resume_flag_documented(self, skill_body: str) -> None:
        assert "--resume" in skill_body
        assert "manifest.yaml" in skill_body
