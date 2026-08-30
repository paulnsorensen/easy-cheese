"""Pin the continuity contract the Wheypoint kernel put into the skill prose.

These docs are the only thing standing between a resumed session and a wrong
checkpoint, and prose rots silently -- nothing else in the suite fails when an
edit quietly reintroduces "most recently modified" as a selection rule. Each
test below names one property the spec makes binding, so a regression reads as
a contract break rather than a diff nobody reviewed.
"""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SKILLS_DIR = REPO_ROOT / "skills"

WHEYPOINT = SKILLS_DIR / "wheypoint" / "SKILL.md"
CHEESE = SKILLS_DIR / "cheese" / "SKILL.md"
CONTINUE_RESUME = SKILLS_DIR / "cheese" / "references" / "continue-resume.md"

# The spec fixes the command set at exactly four. Genesis is a delta whose
# expected_revision_id is the sentinel, so a `create` command must never appear.
COMMANDS = ("commit", "resolve", "show", "lint")


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


@pytest.mark.parametrize("path", [CONTINUE_RESUME, CHEESE])
def test_continuation_never_selects_a_checkpoint_by_recency(path: Path) -> None:
    """Issue 320/375. `continue-resume.md` used to say "scan for the most
    recently modified handoff slug", which is precisely the authority the spec
    forbids: "No path SHALL be chosen by modification time, session, or slug
    recency." A slug is an alias, not an identity."""
    body = _read(path).lower()
    for forbidden in (
        "most recently modified",
        "most recent handoff",
        "newest note",
        "newest match",
        "latest matching",
        "by mtime",
    ):
        assert forbidden not in body, f"{path.name} reintroduced recency authority: {forbidden}"


def test_the_resume_flow_states_the_recency_prohibition_outright() -> None:
    """Absence of the old phrasing is not enough -- a reader following the flow
    has to be told, or the next author reinvents newest-wins as an obvious
    tie-break."""
    body = _read(CONTINUE_RESUME)
    assert "Nothing is selected by recency" in body
    lowered = body.lower()
    assert "modification time" in lowered
    assert "ambiguity" in lowered


def test_resolution_runs_through_the_runtime_rather_than_by_hand() -> None:
    body = _read(CONTINUE_RESUME)
    assert "/wheypoint resolve --ref" in body
    assert "git worktree list --porcelain" in body, "legacy fallback must search sibling worktrees"
    assert ".cheese/notes/" in body


def test_runtime_commands_are_terminal_before_checkpoint_flow() -> None:
    body = _read(SKILLS_DIR / "wheypoint" / "SKILL.md")
    assert "return output, and **STOP** before checkpoint writing" in body
    assert "/cheese --continue" in body



def test_legacy_resolution_requires_an_informed_resume_gate() -> None:
    body = _read(CONTINUE_RESUME).lower()
    assert "a `legacy` result is non-authoritative" in body
    assert "separate informed trust gate" in body
    assert "untrusted context" in body
    assert "live message that explicitly directs manual resume" in body
    assert "normal `/wheypoint` flow" in body


def test_legacy_runtime_gates_cannot_be_waived_by_manual_resume() -> None:
    body = _read(CONTINUE_RESUME).lower()
    assert "any runtime `gated` outcome from a legacy `halt` or `gated` status" in body
    assert "a live directive cannot waive that runtime gate" in body
    assert (
        "manual resume answers only that trust gate" in body
        and "clean runtime `legacy` result with `status: ok`" in body
    )
    assert "never this halt gate or any other runtime integrity gate" in body
    assert "explicit permission to dispatch the next phase" not in body

def test_the_documented_command_set_is_exactly_the_four_the_spec_fixes() -> None:
    """Documented across the continuity docs as a whole: /wheypoint owns the
    write path (commit, show), the resume flow owns the read path (resolve,
    lint). What matters is that all four are reachable and no fifth exists."""
    corpus = "\n".join(_read(path) for path in (WHEYPOINT, CHEESE, CONTINUE_RESUME))
    for command in COMMANDS:
        marker = f"wheypoint.pyz {command}"
        portable_marker = f"/wheypoint {command}"
        assert marker in corpus or portable_marker in corpus, f"undocumented command: {command}"
    assert "wheypoint.pyz create" not in corpus, (
        "genesis is a delta naming the sentinel, not a fifth command"
    )


def test_wheypoint_invokes_only_its_repo_relative_archive() -> None:
    body = _read(WHEYPOINT)
    command = "python3 skills/wheypoint/scripts/wheypoint.pyz"

    assert "${CLAUDE_SKILL_DIR}" not in body
    assert "bundle fallback" not in body
    assert "wheypoint.pyz " not in body.replace(command, "")


def test_the_genesis_sentinel_is_documented_as_the_way_work_starts() -> None:
    """Without this, a reader finds expected_revision_id required and no way to
    satisfy it on a first checkpoint."""
    body = _read(WHEYPOINT)
    assert "genesis" in body.lower()
    assert "expected_revision_id" in body


@pytest.mark.parametrize(
    "stopper",
    ["ambiguity", "digest", "gated", "artifact coverage"],
)
def test_the_flow_names_what_stops_automatic_dispatch(stopper: str) -> None:
    """Acceptance: ambiguity, unresolved lineage, integrity failures, and gates
    stop automatic dispatch."""
    body = _read(CONTINUE_RESUME).lower()
    assert stopper in body, f"resume flow does not name {stopper!r} as a dispatch stopper"
    assert "dispatch nothing" in body or "dispatches nothing" in body


@pytest.mark.parametrize("path", [WHEYPOINT, CONTINUE_RESUME])
def test_the_docs_prohibit_reaching_for_git_to_make_a_resume_work(path: Path) -> None:
    """Durability is reported -- canonical-local, repo-snapshot, published --
    and never enacted. The runtime enforces this; the prose must not invite a
    reader to work around it by hand."""
    body = _read(path).lower()
    assert "never commit, push, or publish" in body or "never run a git commit" in body


def test_markdown_is_documented_as_a_projection_not_the_authority() -> None:
    body = _read(WHEYPOINT).lower()
    assert "projection" in body
    assert "not the authority" in body or "never the authority" in body


def test_the_shared_handoff_api_is_documented_as_unchanged() -> None:
    """The spec preserves shared/scripts/handoff.py and paths.py exports: the
    child adds a continuity codec rather than widening legacy phase parsing.
    parse_handoff_slug() has live callers that must keep working."""
    body = _read(WHEYPOINT)
    assert "parse_handoff_slug" in body or "shared/scripts/handoff.py" in body


def test_split_and_join_are_marked_outside_the_continuity_contract() -> None:
    """The spec's non-goals exclude split/join from this kernel. They survive as
    pre-existing note-level verbs, so the docs must say they commit no delta
    rather than leave a reader assuming the runtime handles them."""
    body = _read(WHEYPOINT)
    assert "--join" in body and "--split" in body, "the legacy verbs still exist elsewhere"
    assert "outside this continuity contract" in body
    assert "commit no delta" in body

def test_pipeline_omits_cut_and_resume_preserves_flags() -> None:
    wheypoint = _read(WHEYPOINT)
    cheese = _read(CHEESE)
    resume = _read(CONTINUE_RESUME)
    corpus = "\n".join((wheypoint, cheese, resume))

    assert "next: mold | cook" in wheypoint
    assert "culture -> mold -> cook -> press -> age -> cure -> plate" in corpus
    assert "next: cut" not in corpus
    assert "GateReceipt" not in corpus
    for flag in ("mode:", "--auto", "--hard", "--open-pr", "--safe"):
        assert flag in corpus
    assert "continue: press-corrective-cook" in corpus
    assert "not a global Press-to-Cook dispatch" in corpus
