"""Regression cover for the Cook prose contracts that the r014 review found broken.

Each test locks one blocker or high finding from `review-cook.md` or an
`edge-cook-*.md` note, so a later edit cannot silently restore the defect.
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import cast

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
COOK = REPO_ROOT / "skills" / "cook"
SKILL = COOK / "SKILL.md"
REFERENCES = COOK / "references"
PROSE = (SKILL, *sorted(REFERENCES.glob("*.md")))


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_auto_mode_never_grants_publication_permission() -> None:
    """`--open-pr` is user permission; auto mode must not append it."""
    auto = _read(REFERENCES / "auto-mode.md")

    assert "Cook appends `--open-pr` only when the user supplied that flag." in auto
    assert "`--open-pr` is publication permission, and auto mode never creates it." in auto
    assert "Cook appends `--open-pr` so terminal" not in auto
    assert "Auto mode never adds this flag." in _read(SKILL)


def test_auto_mode_forwards_hard_and_the_slug_to_every_age_dispatch() -> None:
    auto = _read(REFERENCES / "auto-mode.md")

    assert "It then invokes `/age <slug> --scope <touched-paths> --auto`" in auto
    assert (
        "Never dispatch `/age --scope <touched-paths> --auto` without the slug." in auto
    )
    carries = "Every Age dispatch carries the pipeline slug, `--auto`, and any user-supplied `--hard`."
    assert carries in auto


def test_the_typed_cook_handoff_is_the_only_live_recovery_record() -> None:
    """Fan mode must not write live state into the retired Ultracook manifest."""
    gates = _read(REFERENCES / "quality-gates.md")

    assert "The typed Cook handoff is the only live recovery record." in gates
    assert "Never read that manifest to select the phase to execute." in gates
    assert "Fan mode records this snapshot once before any curd cooks." in gates
    assert "ultracook: pre-Seed manifest write" not in gates
    assert "Use the manifest for ultracook." not in gates


def test_the_baseline_key_holds_one_artifact_path() -> None:
    """The handoff preamble accepts one physical line, so no nested mapping."""
    gates = _read(REFERENCES / "quality-gates.md")
    skill = _read(SKILL)

    assert "Therefore `baseline:` holds one artifact reference, not a nested mapping." in gates
    assert "baseline: .cheese/cook/<slug>-baseline.yaml" in gates
    assert "baseline: none | <path to the baseline artifact" in skill
    assert "so never inline the mapping" in skill


def test_the_repair_dispatch_records_the_originating_run_branch() -> None:
    gates = _read(REFERENCES / "quality-gates.md")

    assert "run_branch: <originating run branch>" in gates
    assert "`repair_dispatch: {slug, branch, run_branch}`" in gates
    assert "Read `run_branch` from the baseline artifact." in gates
    assert "Halt when that field is absent." in gates


def test_the_harvest_step_names_the_bundled_command() -> None:
    """`worktree_harvest(...)` is not an interface Cook exposes."""
    gates = _read(REFERENCES / "quality-gates.md")

    assert "worktree_harvest(" not in gates
    assert "cook.pyz worktree harvest \\" in gates
    assert "--branch <repair-branch> --onto <run-branch> --repo <run-worktree>" in gates


def test_the_overlap_rule_defines_its_calculation() -> None:
    gates = _read(REFERENCES / "quality-gates.md")

    assert "git diff --numstat <merge-base>..<repair-branch>" in gates
    assert "Count a rename as one changed file" in gates
    assert "Count a binary file as one changed file and 50 changed lines." in gates


def test_the_documented_handoff_reader_command_parses() -> None:
    """`read-handoff-slug` requires --phase and --slug, not a positional path."""
    from easy_cheese.shared import read_handoff_slug

    fan = _read(REFERENCES / "fan-pathway.md")
    assert "read-handoff-slug --phase <phase> --slug <slug>" in fan
    assert "cook.pyz read-handoff-slug <path>" not in fan

    parser = argparse.ArgumentParser()
    read_handoff_slug._setup(parser)  # pyright: ignore[reportPrivateUsage]
    flags = {
        action.option_strings[0]
        for action in parser._actions
        if action.option_strings
    }
    assert {"--phase", "--slug"} <= flags
    with pytest.raises(SystemExit):
        _ = parser.parse_args([".cheese/cook/demo.md"])


def test_the_handoff_writer_call_keeps_the_report_body() -> None:
    skill = _read(SKILL)

    assert "--body-file <path to the package report body>" in skill
    assert "Pass `--body-file` to keep the package report in the same file." in skill


def test_the_artifact_key_names_the_consumed_upstream_artifact() -> None:
    skill = _read(SKILL)

    assert "`artifact:` names the upstream artifact that this run consumed." in skill
    assert "Do not point `artifact:` at this Cook report." in skill
    assert "path-to-richer-report-if-any" not in skill


def test_terminal_plate_dispatch_has_one_owner_per_route() -> None:
    skill = _read(SKILL)
    fan = _read(REFERENCES / "fan-pathway.md")

    assert "In the linear chain, Cook does not invoke `/plate`." in skill
    assert "In the fan pathway, the Cook orchestrator owns its own terminal `/plate` dispatch." in skill
    assert "The Cook fan orchestrator owns the terminal `/plate` dispatch." in fan
    assert "Terminal Cure owns publication only in the linear chain." in fan


def test_the_planner_request_kind_is_defined_for_every_failure_class() -> None:
    """`PlannerRequest` rejects a kind whose conditional fields are absent."""
    from easy_cheese_schemas import PlannerRequestKind

    fan = _read(REFERENCES / "fan-pathway.md")
    assert "## Planner request kinds" in fan
    for kind in PlannerRequestKind:
        assert f"`{kind.value}`" in fan, kind
    assert "Mold owns planning after a Cook failure." in fan
    assert "at least one `evidence` entry" in fan
    assert "Use `status: ok`, because `gated` and `halt` stop the chain." in fan


def test_the_cook_contract_admits_the_mold_route() -> None:
    skill = _read(SKILL)

    assert "handoff(next = press | age | mold)" in skill
    assert "Cook returns `next: mold` only for a specification failure." in skill


def test_cook_declares_the_wiki_hits_context_payload() -> None:
    """Cheese sends `handoff_context.wiki_hits`, so Cook must declare it."""
    skill = _read(SKILL)

    assert "`handoff_context.wiki_hits` carries `{page, line, why}` entries" in skill
    assert "The key is optional, and its default is absent." in skill
    assert "Reject an entry that omits `page`, `line`, or `why`." in skill


def test_the_repair_dispatch_passes_a_handoff_path_not_a_slug() -> None:
    """Cook resolves a bare slug as a spec, so Pasteurize must send a path."""
    gates = _read(REFERENCES / "quality-gates.md")

    assert "/cook <repair-handoff-path> --auto --open-pr" in gates
    assert "Pass the canonical Pasteurize handoff path, not a bare slug." in gates
    assert "/cook <repair-slug> --auto --open-pr" not in gates


def test_every_relative_reference_link_resolves() -> None:
    """A named section or file must exist on disk."""
    pattern = re.compile(r"\]\((?!https?://)([^)#\s]+)")
    missing: list[str] = []
    for path in PROSE:
        targets = cast("list[str]", pattern.findall(_read(path)))
        for target in targets:
            if not (path.parent / target).resolve().exists():
                missing.append(f"{path.relative_to(REPO_ROOT)} -> {target}")
    assert missing == []


def test_no_cook_prose_names_a_retired_ultracook_heading() -> None:
    for path in PROSE:
        assert "### When invoked from /ultracook" not in _read(path), path
    assert "skills/age/SKILL.md § Router call" not in _read(REFERENCES / "tdd-loop.md")
