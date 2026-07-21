"""Contract-document tests for the in-session auto-chain fresh-context reviewer.

`/cook --auto` runs its whole chain in one window, so today every `/age` pass
reviews the diff in the same context that produced the cook reasoning — the one
place the corpus still allows same-context review below age's scale threshold.
The auto-age-fresh-reviewer spec closes that gap: whenever the host exposes a
sub-agent primitive, the driver that reaches an age pass (press's initial
review, cure's verification) spawns it as a fresh-context, read-only reviewer
carrying ultracook's no-chain directive, reads the handoff slug deterministically
(never the sub-agent's stdout), and drives the next step itself. Cap ownership
moves with the dispatch: a fresh age cannot count prior passes, so the in-session
chain frame — not age — owns the two-cure-pass cap.

These tests are string-shaped rather than parser-shaped (matching
test_ultracook_skills.py): the goal is to catch silent removal of a contract
clause, not to model the SKILL grammar. The single authoritative copy of the
spawn contract lives in age's `## Auto mode`; press and cure link to it, so a
relay-contract drift across the four files is what these guard against.
"""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SKILLS_DIR = REPO_ROOT / "skills"


def _skill(name: str) -> str:
    return (SKILLS_DIR / name / "SKILL.md").read_text(encoding="utf-8")


def _auto_mode(name: str) -> str:
    """The `## Auto mode` section body (through its `###` subsections) up to the
    next top-level `## ` heading. Slicing by the top-level heading keeps the
    ultracook no-chain subsection inside the returned span while excluding
    unrelated sections such as `## Rules`."""
    body = _skill(name)
    start = body.find("\n## Auto mode")
    assert start != -1, f"{name} must have a `## Auto mode` section"
    rest = body[start + 1 :]
    end = rest.find("\n## ", 1)
    return rest if end == -1 else rest[:end]


# ---------------------------------------------------------------------------
# age owns the authoritative spawn contract (single copy press/cure link to)
# ---------------------------------------------------------------------------


class TestAgeSpawnContract:
    def test_auto_mode_documents_a_spawn_contract(self) -> None:
        auto = _auto_mode("age").lower()
        assert "spawn contract" in auto, (
            "age's Auto mode must define the authoritative spawn contract that "
            "press and cure reuse"
        )

    def test_spawn_is_fresh_context_read_only_reviewer(self) -> None:
        auto = _auto_mode("age").lower()
        assert "fresh-context reviewer" in auto, (
            "the auto age pass must be dispatched as a fresh-context reviewer"
        )
        assert "read-only" in auto, "the spawned reviewer must be read-only"

    def test_spawn_carries_ultracook_no_chain_directive(self) -> None:
        auto = _auto_mode("age")
        assert "../ultracook/SKILL.md" in auto, (
            "age's spawn contract must reuse ultracook's no-chain directive by "
            "reference (the sibling-relative path must resolve on a wholesale install)"
        )
        assert "no-chain" in auto.lower(), (
            "the spawn contract must name the no-chain directive it reuses"
        )

    def test_slug_is_read_deterministically_not_from_stdout(self) -> None:
        auto = _auto_mode("age")
        assert "handoff_cli.py parse" in auto, (
            "the driver must read the age handoff slug with handoff_cli parse, "
            "not by eyeballing the sub-agent's output"
        )
        auto_lower = auto.lower()
        assert "stdout" in auto_lower or "final message" in auto_lower, (
            "the spawn contract must forbid inferring the next step from the "
            "sub-agent's stdout / final message"
        )

    def test_degrade_is_inline_and_loud_never_a_halt(self) -> None:
        auto = _auto_mode("age").lower()
        assert "no sub-agent primitive" in auto, (
            "the spawn contract must document the no-sub-agent-primitive degrade"
        )
        assert "inline" in auto, "the degrade must run age inline (same-window review)"

    def test_age_no_longer_self_counts_cure_passes(self) -> None:
        auto = _auto_mode("age")
        # The old self-count clauses must be gone — a fresh age cannot see prior
        # passes, so the cap moved to the driving chain frame.
        assert "increment the cure-pass count" not in auto, (
            "age must not claim to increment a cure-pass count it cannot observe"
        )
        assert "If two cure passes have already completed" not in auto, (
            "age must not self-gate on a cure-pass count (cap moved to the chain frame)"
        )

    def test_age_attributes_the_cap_to_the_driver_not_itself(self) -> None:
        auto = _auto_mode("age").lower()
        assert "cannot count" in auto or "does not count" in auto, (
            "age must state it does not count cure passes"
        )
        assert "chain frame" in auto or "driver" in auto, (
            "age must attribute cap ownership to the driving chain frame"
        )


# ---------------------------------------------------------------------------
# press drives the initial review through age's spawn contract
# ---------------------------------------------------------------------------


class TestPressDrivesInitialReview:
    def test_press_links_to_age_spawn_contract(self) -> None:
        auto = _auto_mode("press")
        assert "../age/SKILL.md" in auto, (
            "press must reuse the authoritative spawn contract in age's Auto "
            "mode by reference, not duplicate it"
        )

    def test_press_dispatches_a_fresh_reviewer(self) -> None:
        auto = _auto_mode("press").lower()
        assert "fresh-context reviewer" in auto or "spawn contract" in auto, (
            "press's Auto mode must dispatch the initial age as a fresh reviewer"
        )

    def test_press_drives_the_cure_step_itself(self) -> None:
        auto = _auto_mode("press")
        assert "/cure <slug> --auto --stake medium+" in auto, (
            "on next: cure the driver (press) must invoke cure itself — age no "
            "longer chains forward"
        )


# ---------------------------------------------------------------------------
# cure drives the verification review and the chain frame owns the cap
# ---------------------------------------------------------------------------


class TestCureDrivesVerification:
    def test_cure_links_to_age_spawn_contract(self) -> None:
        auto = _auto_mode("cure")
        assert "../age/SKILL.md" in auto, (
            "cure's verification age must run through age's spawn contract by "
            "reference, not a duplicated block"
        )

    def test_cure_verification_is_fresh_context(self) -> None:
        auto = _auto_mode("cure").lower()
        assert "fresh-context reviewer" in auto or "spawn contract" in auto, (
            "cure's verification age must be a fresh-context reviewer too — "
            "verification passes gate publication"
        )

    def test_chain_frame_owns_the_two_cure_pass_cap(self) -> None:
        auto = _auto_mode("cure").lower()
        assert "chain frame" in auto, (
            "cure must attribute the two-cure-pass cap to the in-session chain "
            "frame (mirroring ultracook's chain-length rule)"
        )
        assert "two" in auto and "cure" in auto and "cap" in auto, (
            "cure must state the cap is two cure passes"
        )

    def test_cure_no_longer_pins_the_cap_on_age(self) -> None:
        # The relocated cap must not leave the stale "age enforces it" claim
        # anywhere in cure, or the two contracts contradict.
        body = _skill("cure")
        assert "enforced by `/age --auto`'s third invocation" not in body, (
            "cure must not still attribute cap enforcement to /age --auto"
        )


# ---------------------------------------------------------------------------
# cook's Auto mode description stays in sync with the relocated contract
# ---------------------------------------------------------------------------


class TestCookDescriptionSync:
    def test_cook_names_the_fresh_reviewer_dispatch(self) -> None:
        auto = _auto_mode("cook").lower()
        assert "fresh-context reviewer" in auto, (
            "cook's Auto mode summary must describe the age pass as a "
            "fresh-context reviewer dispatch"
        )

    def test_cook_documents_the_degrade(self) -> None:
        auto = _auto_mode("cook").lower()
        assert "no sub-agent primitive" in auto and "inline" in auto, (
            "cook's Auto mode must note the inline degrade when no sub-agent "
            "primitive exists"
        )

    def test_cook_attributes_the_cap_to_the_chain_frame(self) -> None:
        auto = _auto_mode("cook").lower()
        assert "chain frame" in auto, (
            "cook's cap description must attribute the two-cure-pass cap to the "
            "chain frame, not to age"
        )


# ---------------------------------------------------------------------------
# Relay-contract integrity — the spec's headline risk
# ---------------------------------------------------------------------------


class TestSingleAuthoritativeCopy:
    def test_only_age_hosts_the_helper_invocation(self) -> None:
        # handoff_cli.py parse is the spawn contract's slug-read step; it lives
        # in age (the authoritative copy). press/cure link rather than re-cite,
        # so drift can only happen in one place.
        assert "handoff_cli.py parse" in _auto_mode("age")
        assert "handoff_cli.py parse" not in _auto_mode("press"), (
            "press must link to age's spawn contract, not duplicate the helper"
        )
        assert "handoff_cli.py parse" not in _auto_mode("cure"), (
            "cure must link to age's spawn contract, not duplicate the helper"
        )

    @pytest.mark.parametrize("phase", ["press", "cure", "cook"])
    def test_drivers_point_at_ages_auto_mode(self, phase: str) -> None:
        assert "../age/SKILL.md" in _auto_mode(phase), (
            f"{phase} must cross-reference age's Auto mode spawn contract"
        )


# ---------------------------------------------------------------------------
# Press hardening — boundaries and non-goals the initial cut left implicit
# ---------------------------------------------------------------------------


class TestPressHardening:
    """Pins the spec's non-goals and the degrade's never-halt decision, plus
    the co-location of each driver's cross-reference with spawn-contract
    wording, so a future rewrite of an Auto-mode section cannot silently drop
    them while still satisfying the presence checks above."""

    def test_age_preserves_medium_floor_next_semantics(self) -> None:
        # Non-goal: "No change to the next:/severity-floor semantics of the age
        # report." The rewrite must keep next: cure <-> medium+ floor met and
        # next: done <-> none met.
        auto = _auto_mode("age")
        assert "medium+ floor" in auto, (
            "age must still gate next: on the medium+ floor"
        )
        assert "`next: cure`" in auto and "`next: done`" in auto, (
            "age must still document both next: cure and next: done outcomes"
        )

    def test_degrade_is_never_a_halt(self) -> None:
        # Decision: "Degrade is inline-plus-loud-note, never a halt." age owns
        # the clause; cook's summary must not contradict it.
        assert "never halt" in _auto_mode("age").lower(), (
            "age's degrade clause must state it never halts"
        )
        cook_auto = _auto_mode("cook").lower()
        assert "keeps running" in cook_auto or "keep working" in cook_auto, (
            "cook's degrade summary must state the chain keeps running"
        )

    @pytest.mark.parametrize("phase", ["press", "cure", "cook"])
    def test_driver_cross_reference_is_the_spawn_contract_link(self, phase: str) -> None:
        # Strengthens the single-copy check: the ../age/SKILL.md ref in each
        # driver must be the spawn-contract link, not an incidental mention, so
        # the authoritative copy stays the one press/cure/cook actually reuse.
        auto = _auto_mode(phase)
        assert "../age/SKILL.md" in auto and "spawn contract" in auto.lower(), (
            f"{phase} must cite ../age/SKILL.md specifically as the spawn contract"
        )


# ---------------------------------------------------------------------------
# Non-goals — the interactive and ultracook paths stay untouched
# ---------------------------------------------------------------------------


class TestNonGoalsPreserved:
    @pytest.mark.parametrize("phase", ["age", "press", "cure", "cook"])
    def test_ultracook_no_chain_override_still_documented(self, phase: str) -> None:
        # The spec must not disturb the ultracook no-chain contract each phase
        # already documents (guarded independently by test_ultracook_skills.py;
        # duplicated here so a regression surfaces against this spec too).
        body = _skill(phase).lower()
        assert "/ultracook" in body
        assert "no-chain" in body or "from /ultracook" in body

    def test_age_does_not_leak_chain_table_internals(self) -> None:
        # Encapsulation: age must not name ultracook's specific spawn numbers.
        body = _skill("age")
        for spawn in ("spawn #3", "spawn #5", "spawn #7"):
            assert spawn not in body
