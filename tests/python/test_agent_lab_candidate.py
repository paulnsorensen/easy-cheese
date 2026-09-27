"""Offline checks for the candidate allowlist, token-budget guard, and build gate.

The default suite fakes every build subprocess through the `run` seam; one
opt-in test (AGENT_LAB_REAL_BUILD=1) runs the real build_pyz/pytest steps.
"""

from __future__ import annotations

import json
import os
import subprocess
from collections.abc import Sequence
from pathlib import Path
from typing import cast

import pytest

from agent_lab_candidate import (
    BUILD_GUARD,
    CODE_PREFIX,
    SKILL_MD_PATH,
    TOKEN_BUDGET_GUARD,
    CandidateError,
    CommandRunner,
    build_candidate,
    has_code_changes,
    load_candidate_dir,
    prepare_overlay,
    token_budget_guard,
    validate_candidate,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
COMMANDS_PATH = f"{CODE_PREFIX}commands.py"
ORIGINAL_SKILL_MD = (REPO_ROOT / SKILL_MD_PATH).read_text(encoding="utf-8")
ORIGINAL_COMMANDS = (REPO_ROOT / COMMANDS_PATH).read_text(encoding="utf-8")


def _fake_run(calls: list[list[str]], *, fail_on: str | None = None) -> CommandRunner:
    """A `run` seam that logs argv, simulates build_pyz/render/pytest, and can
    fail on the step whose argv contains `fail_on`.
    """

    def run(argv: Sequence[str], cwd: Path) -> "subprocess.CompletedProcess[str]":
        calls.append(list(argv))
        joined = " ".join(argv)
        if fail_on is not None and fail_on in joined:
            return subprocess.CompletedProcess(argv, 1, "", "simulated failure")
        if "render_generated_regions.py" in joined:
            commands_md = cwd / "skills" / "cook" / "references" / "commands.md"
            _ = commands_md.write_text("REGENERATED-MARKER\n", encoding="utf-8")
        if "build_pyz.py" in joined and "--out-dir" in argv:
            out_dir = Path(argv[argv.index("--out-dir") + 1])
            out_dir.mkdir(parents=True, exist_ok=True)
            _ = (out_dir / "cook.pyz").write_bytes(b"fake-pyz")
        return subprocess.CompletedProcess(argv, 0, "", "")

    return run


class TestValidateCandidate:
    def test_accepts_allowed_paths(self) -> None:
        validate_candidate(
            {
                SKILL_MD_PATH: "text",
                "skills/cook/references/tdd-loop.md": "text",
                COMMANDS_PATH: "text",
            }
        )

    @pytest.mark.parametrize(
        "rel_path",
        ["/etc/passwd", "../outside.md", "skills/cook/scripts/cook.pyz", "src/easy_cheese/shared/paths.py"],
    )
    def test_rejects_out_of_reach_paths(self, rel_path: str) -> None:
        with pytest.raises(CandidateError, match="out of reach"):
            validate_candidate({rel_path: "text"})


class TestHasCodeChanges:
    def test_code_text_matching_head_is_no_change(self) -> None:
        assert not has_code_changes(REPO_ROOT, {COMMANDS_PATH: ORIGINAL_COMMANDS})

    def test_code_text_differing_from_head_is_change(self) -> None:
        assert has_code_changes(REPO_ROOT, {COMMANDS_PATH: ORIGINAL_COMMANDS + "\n# mutated\n"})

    def test_non_code_path_is_not_change(self) -> None:
        assert not has_code_changes(REPO_ROOT, {SKILL_MD_PATH: "x"})


class TestLoadCandidateDir:
    def test_loads_current_checkout(self) -> None:
        candidate = load_candidate_dir(REPO_ROOT)
        assert candidate[SKILL_MD_PATH] == ORIGINAL_SKILL_MD
        assert candidate[COMMANDS_PATH] == ORIGINAL_COMMANDS
        assert all(path == SKILL_MD_PATH or path.startswith(CODE_PREFIX) or "references" in path for path in candidate)


class TestTokenBudgetGuard:
    def test_within_budget_is_none(self) -> None:
        assert token_budget_guard({SKILL_MD_PATH: "short body"}) is None

    def test_over_budget_returns_guard(self) -> None:
        # ~4 bytes/token estimate; well past the 3600-token cap.
        oversized = "word " * 20_000
        assert token_budget_guard({SKILL_MD_PATH: oversized}) == TOKEN_BUDGET_GUARD

    def test_no_skill_md_is_none(self) -> None:
        assert token_budget_guard({"skills/cook/references/tdd-loop.md": "x"}) is None


class TestBuildCandidate:
    def test_build_produces_overlay_pyz_and_regenerated_commands(self, tmp_path: Path) -> None:
        calls: list[list[str]] = []
        candidate = {COMMANDS_PATH: ORIGINAL_COMMANDS + "\n# candidate marker\n"}
        overlay = tmp_path / "overlay"
        result = build_candidate(
            candidate, repo_root=REPO_ROOT, overlay_dir=overlay, run=_fake_run(calls)
        )
        assert result.guard is None
        pyz = overlay / "skills" / "cook" / "scripts" / "cook.pyz"
        assert pyz.read_bytes() == b"fake-pyz"
        commands_md = overlay / "skills" / "cook" / "references" / "commands.md"
        assert commands_md.read_text(encoding="utf-8") == "REGENERATED-MARKER\n"
        plugin = cast(
            "dict[str, object]",
            json.loads((overlay / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8")),
        )
        assert plugin == {"name": "easy-cheese", "skills": ["./skills/cook"]}
        assert any("--write-generated" in call for call in calls)
        assert any("render_generated_regions.py" in " ".join(call) for call in calls)
        assert any(
            "-m" in call and "pytest" in call and any("test_cook_" in arg for arg in call)
            for call in calls
        ), "a code-changed build must run cook's own tests before the out-dir build"

    def test_build_failure_scores_guard_and_leaves_no_pyz(self, tmp_path: Path) -> None:
        calls: list[list[str]] = []
        candidate = {COMMANDS_PATH: "def broken(:\n"}
        overlay = tmp_path / "overlay"
        result = build_candidate(
            candidate, repo_root=REPO_ROOT, overlay_dir=overlay, run=_fake_run(calls, fail_on="--write-generated")
        )
        assert result.guard == BUILD_GUARD
        assert not (overlay / "skills" / "cook" / "scripts" / "cook.pyz").exists()
        # Only the failing step ran; the later out-dir build step never fired.
        assert not any("--out-dir" in call for call in calls)

    def test_failing_cook_test_step_scores_guard_and_leaves_no_pyz(self, tmp_path: Path) -> None:
        # "test_cook_" appears only in the -m pytest step's file-path
        # arguments, unlike "pytest", which also appears in every step's
        # `--with pytest==9.0.3` uv-run prefix.
        calls: list[list[str]] = []
        candidate = {COMMANDS_PATH: ORIGINAL_COMMANDS + "\n# candidate marker\n"}
        overlay = tmp_path / "overlay"
        result = build_candidate(
            candidate, repo_root=REPO_ROOT, overlay_dir=overlay, run=_fake_run(calls, fail_on="test_cook_")
        )
        assert result.guard == BUILD_GUARD
        assert not (overlay / "skills" / "cook" / "scripts" / "cook.pyz").exists()
        # The failing test step ran; the later out-dir build step never fired.
        assert any("-m" in call and "pytest" in call for call in calls)
        assert not any("--out-dir" in call for call in calls)

    def test_no_code_change_reuses_tracked_pyz_without_building(self, tmp_path: Path) -> None:
        calls: list[list[str]] = []
        candidate = {SKILL_MD_PATH: "a small candidate prompt"}
        overlay = tmp_path / "overlay"
        result = build_candidate(
            candidate, repo_root=REPO_ROOT, overlay_dir=overlay, run=_fake_run(calls)
        )
        assert result.guard is None
        assert not calls
        pyz = overlay / "skills" / "cook" / "scripts" / "cook.pyz"
        assert pyz.read_bytes() == (REPO_ROOT / "skills/cook/scripts/cook.pyz").read_bytes()
        skill_md = overlay / "skills" / "cook" / "SKILL.md"
        assert skill_md.read_text(encoding="utf-8") == "a small candidate prompt"

    def test_code_component_identical_to_head_reuses_tracked_pyz_without_building(
        self, tmp_path: Path
    ) -> None:
        """A candidate seeded from the current checkout (--seed current) or a
        GEPA mutation that only touches SKILL.md carries CODE_PREFIX text
        that is byte-identical to HEAD; that must not trigger a rebuild."""
        calls: list[list[str]] = []
        candidate = {COMMANDS_PATH: ORIGINAL_COMMANDS, SKILL_MD_PATH: "a small candidate prompt"}
        overlay = tmp_path / "overlay"
        result = build_candidate(
            candidate, repo_root=REPO_ROOT, overlay_dir=overlay, run=_fake_run(calls)
        )
        assert result.guard is None
        assert not calls, "an unchanged CODE_PREFIX component must not trigger a rebuild"
        pyz = overlay / "skills" / "cook" / "scripts" / "cook.pyz"
        assert pyz.read_bytes() == (REPO_ROOT / "skills/cook/scripts/cook.pyz").read_bytes()

    def test_checkout_is_never_written(self, tmp_path: Path) -> None:
        before = ORIGINAL_COMMANDS
        candidate = {COMMANDS_PATH: ORIGINAL_COMMANDS + "\n# candidate marker\n"}
        _ = build_candidate(
            candidate, repo_root=REPO_ROOT, overlay_dir=tmp_path / "overlay", run=_fake_run([])
        )
        assert (REPO_ROOT / COMMANDS_PATH).read_text(encoding="utf-8") == before


class TestPrepareOverlay:
    def test_token_budget_guard_makes_zero_build_calls(self, tmp_path: Path) -> None:
        calls: list[list[str]] = []
        oversized = "word " * 20_000
        guard = prepare_overlay(
            {SKILL_MD_PATH: oversized},
            repo_root=REPO_ROOT,
            overlay_dir=tmp_path / "overlay",
            run=_fake_run(calls),
        )
        assert guard == TOKEN_BUDGET_GUARD
        assert not calls
        assert not (tmp_path / "overlay").exists()

    def test_passes_through_to_build(self, tmp_path: Path) -> None:
        guard = prepare_overlay(
            {SKILL_MD_PATH: "a small candidate prompt"},
            repo_root=REPO_ROOT,
            overlay_dir=tmp_path / "overlay",
            run=_fake_run([]),
        )
        assert guard is None


@pytest.mark.skipif(os.environ.get("AGENT_LAB_REAL_BUILD") != "1", reason="set AGENT_LAB_REAL_BUILD=1 to run the real build")
def test_real_build_round_trip(tmp_path: Path) -> None:
    """One opt-in, unfaked pass through build_pyz, render_generated_regions,
    and cook's own tests, to prove the fake seam matches reality.
    """
    candidate = {COMMANDS_PATH: ORIGINAL_COMMANDS + "\n# agent-lab real-build probe: no behavior change\n"}
    overlay = tmp_path / "overlay"
    result = build_candidate(candidate, repo_root=REPO_ROOT, overlay_dir=overlay)
    assert result.guard is None, result.detail
    pyz = overlay / "skills" / "cook" / "scripts" / "cook.pyz"
    assert pyz.stat().st_size > 0
    assert (overlay / "skills" / "cook" / "references" / "commands.md").exists()
