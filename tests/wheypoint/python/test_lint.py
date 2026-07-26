"""Behaviour tests for `wheypoint.pyz lint`.

Each test drives the public surface (`lint_note` / `main`) and asserts on the
finding messages and exit codes a cold reader (or the /wheypoint flow) would see,
not on private helpers. The acceptance criteria they pin come from
skills/wheypoint/SKILL.md and the wheypoint-note-lint spec.
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import ModuleType

import pytest

# --- note fixtures ---------------------------------------------------------

CLEAN_SINGLE = """\
status: ok
next: cook
artifact: none
created: 2026-07-21T00:00:00Z
Approved spec ready to implement.

## Document

Goal. Ship the thing.

Open questions and blockers. None blocking.
"""

CLEAN_PARALLEL = """\
status: ok
next: tasks
mode: parallel
artifact: none
Two approved specs ready to cook in parallel worktrees.
parallel:
  isolation: git-worktree
  worktree_strategy: create
  worktree_root: /tmp/wt
tasks:
  - slug: task-a
    branch: marcus/task-a
    branch_from: origin/main
    command: /cook --auto a.md
  - slug: task-b
    branch: marcus/task-b
    branch_from: origin/main
    command: /cook --auto b.md

## Document

Open questions and blockers. None blocking.
"""


def _write_note(tmp_path: Path, text: str, *, name: str = "note") -> Path:
    notes = tmp_path / ".cheese" / "notes"
    notes.mkdir(parents=True, exist_ok=True)
    note = notes / f"{name}.md"
    note.write_text(text, encoding="utf-8")
    return note


def _findings(lint: ModuleType, text: str, repo_root: Path) -> list[str]:
    findings, _ = lint.lint_note(text, repo_root)
    return findings


# --- header parsing --------------------------------------------------------


def test_clean_single_note_has_no_findings(lint: ModuleType, tmp_path: Path) -> None:
    assert _findings(lint, CLEAN_SINGLE, tmp_path) == []


def test_missing_status_line_is_a_finding(lint: ModuleType, tmp_path: Path) -> None:
    text = "next: cook\nartifact: none\nOrientation line.\n"
    assert any("status:" in f for f in _findings(lint, text, tmp_path))


def test_missing_next_line_is_a_finding(lint: ModuleType, tmp_path: Path) -> None:
    text = "status: ok\nartifact: none\nOrientation line.\n"
    assert any("next:" in f for f in _findings(lint, text, tmp_path))


def test_missing_orientation_is_a_finding(lint: ModuleType, tmp_path: Path) -> None:
    text = "status: ok\nnext: cook\nartifact: none\n"
    assert any("orientation" in f for f in _findings(lint, text, tmp_path))


def test_heading_immediately_after_preamble_is_missing_orientation(
    lint: ModuleType, tmp_path: Path
) -> None:
    """A `##` heading cannot stand in for the orientation line — it is body, and
    binding it as orientation is the silent-consumption failure the strict
    physical-line parse exists to stop."""
    text = "status: ok\nnext: cook\nartifact: none\n## Document\n\nGoal.\n"
    assert any("orientation" in f for f in _findings(lint, text, tmp_path))


# --- status grammar --------------------------------------------------------


def test_status_gated_with_reason_is_accepted(lint: ModuleType, tmp_path: Path) -> None:
    text = "status: gated: pick the auth library\nnext: cook\nartifact: none\nBlocked on a call.\n"
    assert not any("status must be" in f for f in _findings(lint, text, tmp_path))


def test_status_halt_with_reason_is_accepted(lint: ModuleType, tmp_path: Path) -> None:
    text = "status: halt: build broke\nnext: cook\nartifact: none\nStopped mid-flight.\n"
    assert not any("status must be" in f for f in _findings(lint, text, tmp_path))


def test_status_gated_without_reason_is_a_finding(lint: ModuleType, tmp_path: Path) -> None:
    text = "status: gated:\nnext: cook\nartifact: none\nOrientation.\n"
    assert any("requires a reason" in f for f in _findings(lint, text, tmp_path))


def test_unknown_status_is_a_finding(lint: ModuleType, tmp_path: Path) -> None:
    text = "status: maybe\nnext: cook\nartifact: none\nOrientation.\n"
    assert any("status must be" in f for f in _findings(lint, text, tmp_path))


# --- next enum / list form -------------------------------------------------


def test_next_outside_enum_is_a_finding(lint: ModuleType, tmp_path: Path) -> None:
    text = "status: ok\nnext: frobnicate\nartifact: none\nOrientation.\n"
    assert any("next: must be one of" in f for f in _findings(lint, text, tmp_path))


def test_next_list_requires_order(lint: ModuleType, tmp_path: Path) -> None:
    text = 'status: ok\nnext: [briesearch "a", culture "b"]\nartifact: none\nOrientation.\n'
    assert any("requires an 'order:'" in f for f in _findings(lint, text, tmp_path))


def test_next_list_rejects_write_skill(lint: ModuleType, tmp_path: Path) -> None:
    text = 'status: ok\nnext: [briesearch "a", cook "b"]\norder: parallel\nartifact: none\nGo.\n'
    assert any("read-only skills" in f for f in _findings(lint, text, tmp_path))


def test_next_list_valid_is_clean(lint: ModuleType, tmp_path: Path) -> None:
    text = 'status: ok\nnext: [briesearch "a", culture "b"]\norder: sequential\nartifact: none\nGo.\n'
    assert _findings(lint, text, tmp_path) == []


def test_next_list_arg_with_comma_is_not_mis_split(lint: ModuleType, tmp_path: Path) -> None:
    """A comma inside a quoted argument must not be read as an item separator —
    the skill tokens are still `briesearch` and `culture`, not a fragment of the
    argument, so no spurious read-only-skill finding fires."""
    text = 'status: ok\nnext: [briesearch "a, b, c", culture "d"]\norder: parallel\nartifact: none\nGo.\n'
    assert _findings(lint, text, tmp_path) == []


def test_next_tasks_requires_parallel_mode(lint: ModuleType, tmp_path: Path) -> None:
    text = "status: ok\nnext: tasks\nartifact: none\nOrientation.\n"
    assert any("mode: parallel" in f for f in _findings(lint, text, tmp_path))


def test_bad_order_value_is_a_finding(lint: ModuleType, tmp_path: Path) -> None:
    text = 'status: ok\nnext: [briesearch "a"]\norder: eventually\nartifact: none\nGo.\n'
    assert any("order: must be" in f for f in _findings(lint, text, tmp_path))


# --- mode ------------------------------------------------------------------


def test_invalid_mode_is_a_finding(lint: ModuleType, tmp_path: Path) -> None:
    text = "status: ok\nnext: cook\nmode: turbo\nartifact: none\nOrientation.\n"
    assert any("mode: must be" in f for f in _findings(lint, text, tmp_path))


# --- parallel requires tasks ----------------------------------------------


def test_parallel_without_tasks_block_is_a_finding(lint: ModuleType, tmp_path: Path) -> None:
    """Presence of the tasks block is checked without PyYAML, so this fires on
    every host — it is the core acceptance clause."""
    text = "status: ok\nnext: tasks\nmode: parallel\nartifact: none\nTwo tracks.\n\n## Document\n\nGoal.\n"
    assert any("requires a 'tasks:' block" in f for f in _findings(lint, text, tmp_path))


def test_clean_parallel_note_has_no_findings(lint: ModuleType, tmp_path: Path) -> None:
    """With or without PyYAML the clean parallel note produces no *findings* (a
    PyYAML-absent host adds an advisory, which is asserted separately)."""
    assert _findings(lint, CLEAN_PARALLEL, tmp_path) == []


def test_parallel_missing_task_fields_is_a_finding(lint: ModuleType, tmp_path: Path) -> None:
    pytest.importorskip("yaml")
    text = CLEAN_PARALLEL.replace(
        "  - slug: task-b\n    branch: marcus/task-b\n    branch_from: origin/main\n    command: /cook --auto b.md\n",
        "  - slug: task-b\n    branch: marcus/task-b\n",
    )
    findings = _findings(lint, text, tmp_path)
    assert any("tasks[2].command" in f for f in findings)
    assert any("tasks[2].branch_from" in f for f in findings)


def test_parallel_existing_strategy_requires_worktree(lint: ModuleType, tmp_path: Path) -> None:
    pytest.importorskip("yaml")
    text = CLEAN_PARALLEL.replace(
        "  worktree_strategy: create\n  worktree_root: /tmp/wt\n",
        "  worktree_strategy: existing\n",
    )
    assert any("worktree" in f and "tasks[" in f for f in _findings(lint, text, tmp_path))


def test_task_fields_degrade_to_advisory_without_pyyaml(
    lint: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When PyYAML is unavailable the per-task check must not silently vanish and
    must not fail a valid note: it emits one loud advisory and zero findings."""
    monkeypatch.setitem(sys.modules, "yaml", None)
    findings, advisories = lint.lint_note(CLEAN_PARALLEL, tmp_path)
    assert findings == []
    assert any("PyYAML unavailable" in a for a in advisories)


# --- artifact / referenced paths ------------------------------------------


def test_missing_artifact_path_is_a_finding(lint: ModuleType, tmp_path: Path) -> None:
    text = "status: ok\nnext: cook\nartifact: .cheese/specs/missing.md\nOrientation.\n"
    assert any("artifact path does not exist" in f for f in _findings(lint, text, tmp_path))


def test_present_artifact_path_is_clean(lint: ModuleType, tmp_path: Path) -> None:
    (tmp_path / ".cheese" / "specs").mkdir(parents=True)
    (tmp_path / ".cheese" / "specs" / "foo.md").write_text("spec", encoding="utf-8")
    text = "status: ok\nnext: cook\nartifact: .cheese/specs/foo.md\nOrientation.\n"
    assert _findings(lint, text, tmp_path) == []


def test_missing_referenced_cheese_path_is_a_finding(lint: ModuleType, tmp_path: Path) -> None:
    text = (
        "status: ok\nnext: cook\nartifact: none\nOrientation.\n\n"
        "## Document\n\nArtifacts. See .cheese/specs/ghost.md for details.\n"
    )
    assert any("referenced path does not exist" in f for f in _findings(lint, text, tmp_path))


def test_pr_ref_and_url_artifacts_are_not_path_checked(lint: ModuleType, tmp_path: Path) -> None:
    for value in ("PR#4211", "https://github.com/x/y/pull/1"):
        text = f"status: ok\nnext: affinage\nartifact: {value}\nOrientation.\n"
        assert _findings(lint, text, tmp_path) == [], value


# --- ok-vs-blockers contradiction -----------------------------------------


def test_ok_with_blocker_language_is_a_finding(lint: ModuleType, tmp_path: Path) -> None:
    text = (
        "status: ok\nnext: cook\nartifact: none\nHalf done.\n\n"
        "## Document\n\nOpen questions and blockers. Still blocked on the schema decision.\n"
    )
    assert any("blocker language" in f for f in _findings(lint, text, tmp_path))


def test_ok_with_waiting_on_language_is_a_finding(lint: ModuleType, tmp_path: Path) -> None:
    text = (
        "status: ok\nnext: cook\nartifact: none\nHalf done.\n\n"
        "## Document\n\nOpen questions. Waiting on the security review.\n"
    )
    assert any("blocker language" in f for f in _findings(lint, text, tmp_path))


def test_ok_with_negated_blocker_is_clean(lint: ModuleType, tmp_path: Path) -> None:
    """'None blocking' records the absence of blockers and must not trip the
    contradiction heuristic — the documented false-positive to avoid."""
    text = (
        "status: ok\nnext: cook\nartifact: none\nAll clear.\n\n"
        "## Document\n\nOpen questions and blockers. None blocking.\n"
    )
    assert _findings(lint, text, tmp_path) == []


def test_gated_status_permits_blocker_language(lint: ModuleType, tmp_path: Path) -> None:
    text = (
        "status: gated: pick auth library\nnext: cook\nartifact: none\nBlocked on a call.\n\n"
        "## Document\n\nOpen questions and blockers. Still blocked on the auth decision.\n"
    )
    assert not any("blocker language" in f for f in _findings(lint, text, tmp_path))


# The regression that shipped the misfire: a decoy 'blocker' word in an earlier
# section (State) must not shadow a real blocker in the dedicated section. Pinned
# across all three section-lead forms — plain lead, heading, and bold lead.

_DECOY_PLAIN = (
    "status: ok\nnext: cook\nartifact: none\nHalf done.\n\n## Document\n\n"
    "Goal. Ship the parser.\n"
    "State. Cleared the parser blocker; the extractor compiles and tests pass.\n"
    "Open questions and blockers. Still blocked on the auth-library decision.\n"
    "Artifacts. None.\n"
)
_DECOY_HEADING = (
    "status: ok\nnext: cook\nartifact: none\nHalf done.\n\n"
    "## State\n\nCleared the main blocker; tests are green.\n\n"
    "## Open questions and blockers\n\nStill blocked on the auth call.\n"
)
_DECOY_BOLD = (
    "status: ok\nnext: cook\nartifact: none\nHalf done.\n\n## Document\n\n"
    "**State.** Cleared the parser blocker; tests pass.\n\n"
    "**Open questions and blockers.** Still blocked on the auth call.\n"
)


@pytest.mark.parametrize("text", [_DECOY_PLAIN, _DECOY_HEADING, _DECOY_BOLD])
def test_real_blocker_after_decoy_section_is_a_finding(
    lint: ModuleType, tmp_path: Path, text: str
) -> None:
    assert any("blocker language" in f for f in _findings(lint, text, tmp_path))


def test_resolved_blocker_in_state_with_clean_section_is_clean(
    lint: ModuleType, tmp_path: Path
) -> None:
    """A 'blocker' mentioned as resolved in State, with a genuinely clear blockers
    section, must not be flagged — the decoy is outside the scanned section and
    the real section is negated."""
    text = (
        "status: ok\nnext: cook\nartifact: none\nAll clear.\n\n## Document\n\n"
        "State. Cleared the parser blocker; tests pass.\n"
        "Open questions and blockers. None blocking.\n"
    )
    assert _findings(lint, text, tmp_path) == []


@pytest.mark.parametrize(
    "phrasing",
    [
        "None blocking.",
        "No blockers.",
        "No known blockers.",
        "No other blockers remain.",
        "No longer blocked; it merged.",
        "Without any blockers now.",
    ],
)
def test_alternate_negated_blockers_are_clean(
    lint: ModuleType, tmp_path: Path, phrasing: str
) -> None:
    text = (
        f"status: ok\nnext: cook\nartifact: none\nAll clear.\n\n"
        f"## Document\n\nOpen questions and blockers. {phrasing}\n"
    )
    assert _findings(lint, text, tmp_path) == [], phrasing


# --- multiple findings all surface ----------------------------------------


def test_every_finding_is_named(lint: ModuleType, tmp_path: Path) -> None:
    """A note that breaks several rules at once names each — the run reports the
    full contract state, not just the first breakage. The breakages are chosen to
    coexist: the ok-vs-blockers check only fires under `status: ok`, so the note
    stays `ok` and breaks the next enum, the artifact path, and the blocker rule."""
    text = (
        "status: ok\nnext: frobnicate\nartifact: .cheese/specs/gone.md\nHalf done.\n\n"
        "## Document\n\nOpen questions and blockers. Still blocked on the design.\n"
    )
    findings = _findings(lint, text, tmp_path)
    assert any("next: must be one of" in f for f in findings)
    assert any("artifact path does not exist" in f for f in findings)
    assert any("blocker language" in f for f in findings)


# --- CLI exit codes --------------------------------------------------------


def test_main_returns_zero_on_clean_note(lint: ModuleType, tmp_path: Path) -> None:
    note = _write_note(tmp_path, CLEAN_SINGLE)
    assert lint.main([str(note)]) == 0


def test_main_returns_one_on_findings(lint: ModuleType, tmp_path: Path) -> None:
    note = _write_note(tmp_path, "status: nope\nnext: cook\nartifact: none\nGo.\n")
    assert lint.main([str(note)]) == 1


def test_main_returns_two_on_unreadable_note(lint: ModuleType, tmp_path: Path) -> None:
    assert lint.main([str(tmp_path / "does-not-exist.md")]) == 2


def test_json_output_reports_findings_and_ok_flag(
    lint: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    note = _write_note(tmp_path, "status: nope\nnext: cook\nartifact: none\nGo.\n")
    lint.main([str(note), "--json"])
    import json

    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is False
    assert any("status must be" in f for f in payload["findings"])
