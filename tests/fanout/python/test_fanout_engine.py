"""Structural tests for the fan-out engine's shipped surface (src/fanout/ + refs).

The fan-out engine (formerly /cheese-factory) ships as /ultracook's engine:
prompt/schema references under skills/ultracook/references/ and scripts under
src/fanout/ bundled into ultracook.pyz. This guards that every promised file is
present so a dropped reference or script surfaces in CI. The /ultracook SKILL
frontmatter and prose are validated by .github/scripts/validate_skills.py and
tests/python/test_ultracook_skills.py respectively.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
REFERENCES_DIR = REPO_ROOT / "skills" / "ultracook" / "references"
SRC_FANOUT = REPO_ROOT / "src" / "fanout"


class TestReferencesPresent:
    """Every prompt / schema reference the parallel mode loads must be present."""

    REQUIRED_REFERENCES = (
        "decomposer-prompt.md",
        "curd-prompt.md",
        "wiring-prompt.md",
        "pr-planner-prompt.md",
        "manifest-schema.json",
        "pr-plan-schema.json",
        "spawn-primitive-reference.md",
    )

    def test_references_present(self) -> None:
        for ref in self.REQUIRED_REFERENCES:
            assert (REFERENCES_DIR / ref).is_file(), (
                f"missing required reference: references/{ref}"
            )


class TestScriptsPresent:
    """Every engine module bundled into ultracook.pyz must exist in src/fanout/."""

    REQUIRED_SCRIPTS = (
        "phase_decision.py",
        "mode.py",
        "worktree.py",
        "milknado.py",
        "validate_decomposition.py",
        "validate_manifest.py",
        "validate_pr_plan.py",
        "pr_plan_to_branches.py",
        "manifest_update.py",
        "wiring_topo_sort.py",
        "curd.py",
        "wiring.py",
    )

    # The CLI validators are marked executable; the dispatcher runs every module
    # from inside the .pyz, so only these carry the exec bit historically.
    EXECUTABLE_SCRIPTS = (
        "validate_decomposition.py",
        "validate_manifest.py",
        "validate_pr_plan.py",
        "pr_plan_to_branches.py",
    )

    def test_scripts_present(self) -> None:
        for script in self.REQUIRED_SCRIPTS:
            assert (SRC_FANOUT / script).is_file(), (
                f"missing required script: src/fanout/{script}"
            )

    def test_cli_validators_executable(self) -> None:
        for script in self.EXECUTABLE_SCRIPTS:
            mode = (SRC_FANOUT / script).stat().st_mode
            assert mode & 0o111, f"src/fanout/{script} must be executable"


class TestSharedHelpersPresent:
    def test_shared_helpers_present(self) -> None:
        for helper in ("manifest_io.py", "schema.py", "cli.py"):
            assert (REPO_ROOT / "shared" / "scripts" / helper).is_file(), (
                f"missing required shared helper: shared/scripts/{helper}"
            )
