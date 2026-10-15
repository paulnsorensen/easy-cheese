"""Pin the schema-5 contract of the /wheel skill prose.

The prose is the only implementation, so each test names one property the
wheel-port spec (AC-20..AC-22) makes binding.
"""

from __future__ import annotations

import re
from pathlib import Path

WHEEL_DIR = Path(__file__).resolve().parents[2] / "skills" / "wheel"
SKILL = (WHEEL_DIR / "SKILL.md").read_text(encoding="utf-8")


def _section(heading: str) -> str:
    match = re.search(rf"^## {re.escape(heading)}\n(.*?)(?=^## |\Z)", SKILL, re.S | re.M)
    assert match, heading
    return match.group(1)


def test_no_blocker_entry_kind_or_dossier_in_wheel_skill() -> None:
    for path in WHEEL_DIR.rglob("*"):
        if path.is_file():
            text = path.read_text(encoding="utf-8")
            assert "decision_dossier" not in text, path
            assert "dossier" not in text, path
            assert not re.search(r"`blocker` (entry|kind)|gating `blocker`", text), path


def test_gating_questions_carry_a_rationale() -> None:
    assert "`blocks_continuation: true` and a `rationale`" in SKILL
    run = _section("Run")
    assert run.count("`blocks_continuation: true` and a rationale") >= 2


def test_run_routes_only_active_gating_entries_to_gate_clearing_step() -> None:
    step1 = _section("Run").split("2. **Read the state.**")[0]
    assert "An integrity finding is any non-advisory finding" in step1
    assert "`stale-commit`" in step1
    assert "`grounded-path-missing`" in step1
    assert "show-and-continue" in step1
    assert "starts with `active gating entries:`" in step1
    assert "Stop on any other gate detail" in step1
    assert "a revision mismatch" in step1
    assert "`gated` outcome is not a stop" not in step1
    assert "Stop at each runtime gate" not in SKILL


def test_gate_answers_map_to_explicit_actions() -> None:
    step2 = _section("Run").split("2. **Read the state.**")[1].split("3. **Rescan.**")[0]
    assert "stop: checkpoint `next: hold` and exit" in step2
    assert "update `notes`" in step2
    assert "`directive` with the verbatim `quote`" in step2
    assert step2.index("verbatim `quote`") < step2.index("`resolve` transition")


def test_rescan_skips_authoring_only_items() -> None:
    run = _section("Run")
    assert "without the authoring-only items" in run
    assert "(authoring only)" in SKILL
    assert "dirty paths inside Scope are accepted" in SKILL


def test_wheel_identified_by_title_and_run_omits_orientation() -> None:
    assert "`record.title` starts with `wheel:`" in _section("Inputs")
    assert "fixed at genesis" in SKILL
    assert "Set the title to `wheel: <goal>`" in SKILL
    assert "omit `orientation`" in _section("Run")
    assert "orientation starts with `wheel:`" not in SKILL


def test_slug_match_must_be_exact() -> None:
    assert "equals the slug exactly" in _section("Inputs")
    assert "exact slug match" in _section("Inputs")
    assert "equals it exactly" in SKILL


def test_done_check_has_no_exit_code_option_and_stall_counter() -> None:
    assert "or the command exits 0" not in SKILL
    assert "no other signal counts" in SKILL
    assert "stall count: <n>" in SKILL
    assert "`Stall count` reaches `K`" in SKILL


def test_publishing_step_requires_quoted_publish_directive_in_blocker_scan() -> None:
    scan = SKILL.split("The blocker scan checks these items.")[1].split("## Run")[0]
    assert "/affinage" in scan
    assert "/plate" in scan
    assert "verbatim publish quote" in scan


def test_progress_is_defined_for_pass_fail_done_checks() -> None:
    assert "graded result" in SKILL
    assert "An exit code alone is not graded" in SKILL
    assert "moves toward the done value" in SKILL


def test_done_check_runs_once_per_iteration() -> None:
    iterate = _section("Run").split("5. **Iterate.**")[1].split("6. **Stop**")[0]
    assert iterate.count("Run the done check once") == 1
    assert "do not run the check a second time" in iterate


def test_list_filters_by_orientation_prefix() -> None:
    inputs = _section("Inputs")
    assert "`record.title` starts with `wheel:`" in inputs
    assert "discard those hits" in inputs


def test_writes_carry_the_read_base_revision() -> None:
    run = _section("Run")
    assert "`revision_id`" in run
    assert "as the base" in run
    assert "from the last read or write" in run.split("2. **Read the state.**")[0]
    assert "from the last read or write" in run.split("5. **Iterate.**")[1]
