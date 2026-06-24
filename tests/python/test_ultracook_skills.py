"""Documentation-lint tests for the ultracook orchestrator and the SKILL.md
changes the ultracook spec requires across the phase chain.

These tests treat each `SKILL.md` as a contract document: they assert that the
load-bearing phrases — handoff-slug schema, the "inheritance, not diminution"
sub-agent contract, the `--continue` flag on `/cheese`, and so on — are
actually written down in the skills that need them.

They are intentionally string-shaped rather than parser-shaped: the goal is to
catch silent removal of contract clauses, not to model the full SKILL grammar.
"""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SKILLS_DIR = REPO_ROOT / "skills"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _skill(name: str) -> str:
    return _read(SKILLS_DIR / name / "SKILL.md")


HANDOFF_SCHEMA_FIELDS = ("status:", "next:", "artifact:")


# ---------------------------------------------------------------------------
# /ultracook — new orchestrator skill
# ---------------------------------------------------------------------------


class TestUltracookSkillExists:
    def test_skill_md_present(self) -> None:
        path = SKILLS_DIR / "ultracook" / "SKILL.md"
        assert path.is_file(), "skills/ultracook/SKILL.md must exist"

    def test_frontmatter_names_skill(self) -> None:
        body = _skill("ultracook")
        assert body.startswith("---\n"), "SKILL.md must lead with YAML frontmatter"
        assert "\nname: ultracook\n" in body
        assert "\nlicense: MIT\n" in body

    def test_description_mentions_orchestrator_and_auto(self) -> None:
        body = _skill("ultracook")
        # Description fires the harness's skill picker — these phrases are
        # what makes /ultracook discoverable for autonomous-pipeline asks.
        assert "ultracook" in body.lower()
        assert "/cook --auto" in body or "cook --auto" in body
        assert "fresh" in body.lower() and "context" in body.lower()


class TestUltracookPhaseChain:
    # The canonical seven spawns, in chain order. Every assertion in this
    # class anchors to these literal invocations rather than bare substrings
    # so unrelated prose mentions of "cook"/"age"/etc. cannot satisfy or
    # break the contract checks.
    CHAIN_INVOCATIONS = (
        "/cook <slug> --auto",
        "/press <slug> --auto",
        "/age <slug> --auto",
        "/cure <slug> --auto",
        "/age <slug> --auto",
        "/cure <slug> --auto",
        "/age <slug> --auto",
    )
    TABLE_HEADER = "## Phases and slug paths"

    def test_lists_seven_phases_in_order(self) -> None:
        body = _skill("ultracook")
        # Anchor to the chain-table section so reordering unrelated prose
        # cannot satisfy or break the ordering check. The seventh spawn
        # (age₃) is the cap-enforcing terminal phase that writes
        # `next: done` after two cure passes complete.
        idx_table = body.find(self.TABLE_HEADER)
        assert idx_table != -1, (
            f"ultracook must have a `{self.TABLE_HEADER}` section to anchor "
            "the chain-table contract check"
        )
        table_section = body[idx_table:]
        cursor = 0
        for invocation in self.CHAIN_INVOCATIONS:
            next_idx = table_section.find(invocation, cursor)
            assert next_idx != -1, (
                f"ultracook chain table missing `{invocation}` after position "
                f"{cursor} (expected order: {self.CHAIN_INVOCATIONS})"
            )
            # Advance past this match so repeated invocations (age₁/₂/₃,
            # cure₁/₂) walk forward through the table rather than re-matching
            # the same row.
            cursor = next_idx + 1

    def test_propagates_auto_through_every_phase(self) -> None:
        body = _skill("ultracook")
        # Every phase invocation in the chain must carry --auto adjacent.
        # Use the canonical `/<phase> <slug> --auto` form so a regression
        # cannot silently drop --auto or reorder it relative to the slug.
        for invocation in set(self.CHAIN_INVOCATIONS):
            assert invocation in body, f"missing `{invocation}` in ultracook chain"
        # Cure floor must be medium+ to match /cook --auto's contract.
        assert "medium+" in body
        # Spawn count: the chain table should mention --auto at least once
        # per spawn (7 spawns) plus the contract prose. A drop below this
        # floor signals a phase silently lost its --auto suffix.
        assert body.count("--auto") >= 7, (
            f"expected --auto >=7 occurrences (1 per chain spawn); got {body.count('--auto')}"
        )


class TestUltracookInheritanceContract:
    def test_calls_out_full_peer_inheritance(self) -> None:
        body = _skill("ultracook")
        assert "inherit" in body.lower(), (
            "Sub-agent contract must spell out inheritance, not diminution."
        )
        assert "not diminut" in body.lower() or "full peer" in body.lower()

    def test_pins_general_purpose_subagent(self) -> None:
        body = _skill("ultracook")
        assert "general-purpose" in body, (
            "Sub-agents must spawn as general-purpose, not specialized workers."
        )

    def test_forbids_model_downgrade(self) -> None:
        body = _skill("ultracook")
        # The contract bans haiku / scoped tools / restricted MCPs explicitly.
        assert "do not downgrade" in body.lower() or "never downgrade" in body.lower()


class TestUltracookHandoffSchema:
    def test_documents_five_line_slug_shape(self) -> None:
        body = _skill("ultracook")
        for field in HANDOFF_SCHEMA_FIELDS:
            assert field in body, f"handoff schema missing `{field}` field"
        # Both halt and ok terminal states must be reachable.
        assert "halt" in body.lower()
        assert "next:" in body and "done" in body

    def test_paths_are_under_dot_cheese_phase_slug(self) -> None:
        body = _skill("ultracook")
        # Each phase's handoff lives at a predictable path; the orchestrator
        # has to know where to read after spawning.
        for phase in ("cook", "press", "age", "cure"):
            assert f".cheese/{phase}/" in body, (
                f"missing .cheese/{phase}/<slug>.md handoff path"
            )


class TestUltracookExistingHandoffsGuard:
    def test_refuses_to_wipe_existing_handoffs(self) -> None:
        body = _skill("ultracook")
        # If handoffs already exist for the slug, ultracook stops and points
        # the user at /cheese --continue or a manual rm. No flag-driven wipe.
        assert "/cheese --continue" in body
        # Spell out the manual reset path — `rm` is an explicit instruction.
        assert "rm" in body.lower()
        # No surprise --restart flag (we explicitly dropped that idea).
        assert "--restart" not in body


# ---------------------------------------------------------------------------
# /cook — must write its handoff slug
# ---------------------------------------------------------------------------


class TestCookHandoffSlug:
    def test_writes_dot_cheese_cook_slug(self) -> None:
        body = _skill("cook")
        assert ".cheese/cook/" in body, (
            "cook must declare it writes .cheese/cook/<slug>.md"
        )

    def test_handoff_schema_fields_named(self) -> None:
        body = _skill("cook")
        for field in HANDOFF_SCHEMA_FIELDS:
            assert field in body, f"cook handoff schema missing `{field}`"


# ---------------------------------------------------------------------------
# /cure — must write its handoff slug
# ---------------------------------------------------------------------------


class TestCureHandoffSlug:
    def test_writes_dot_cheese_cure_slug(self) -> None:
        body = _skill("cure")
        assert ".cheese/cure/" in body, (
            "cure must declare it writes .cheese/cure/<slug>.md"
        )

    def test_handoff_schema_fields_named(self) -> None:
        body = _skill("cure")
        for field in HANDOFF_SCHEMA_FIELDS:
            assert field in body, f"cure handoff schema missing `{field}`"


# ---------------------------------------------------------------------------
# /culture — invariant relaxed for opt-in notes handoff
# ---------------------------------------------------------------------------


class TestCultureNotesHandoff:
    def test_allows_optional_notes_slug(self) -> None:
        body = _skill("culture")
        assert ".cheese/notes/" in body, (
            "culture must allow an opt-in .cheese/notes/<slug>.md handoff"
        )

    def test_invariant_no_longer_absolute(self) -> None:
        body = _skill("culture")
        # Old wording was "never writes", "writes nothing". The relaxed
        # version explicitly carves out the optional notes slug, so the
        # absolute claim should be qualified somewhere.
        assert "opt-in" in body.lower() or "optional" in body.lower(), (
            "culture's no-write invariant must be qualified for the notes handoff"
        )

    def test_still_forbids_production_writes(self) -> None:
        body = _skill("culture")
        # The relaxation is narrow — production code stays off-limits.
        # Either phrasing is acceptable as long as the carve-out is explicit.
        assert "no commits" in body.lower() or "does not commit" in body.lower()
        assert "production" in body.lower()


# ---------------------------------------------------------------------------
# /mold — high-blast-radius handoff offers ultracook + /cheese --continue
# ---------------------------------------------------------------------------


class TestMoldHighBlastHandoff:
    def test_offers_ultracook(self) -> None:
        body = _skill("mold")
        assert "/ultracook" in body, (
            "mold's handoff must offer /ultracook for high-blast-radius specs"
        )

    def test_offers_continue_flow(self) -> None:
        body = _skill("mold")
        assert "/cheese --continue" in body, (
            "mold's handoff must offer the /cheese --continue compaction path"
        )


# ---------------------------------------------------------------------------
# /cheese — --continue <slug> flag for fresh-context resumption
# ---------------------------------------------------------------------------


class TestCheeseContinueFlag:
    def test_documents_continue_flag(self) -> None:
        body = _skill("cheese")
        assert "--continue" in body, (
            "cheese must document the --continue <slug> resumption flag"
        )

    def test_continue_reads_handoff_slugs(self) -> None:
        body = _skill("cheese")
        # The --continue flow keys off the existing .cheese/<phase>/<slug>.md
        # handoff files — that's the resumability contract.
        assert ".cheese/" in body and "<slug>" in body

    def test_parallel_mode_dispatches_multiple_tasks(self) -> None:
        body = _skill("cheese")
        body_lower = body.lower()
        assert "mode: parallel" in body, (
            "cheese --continue must document the parallel continuation mode"
        )
        assert "tasks:" in body, (
            "parallel continuation must carry explicit task commands"
        )
        assert "same response" in body_lower or "same turn" in body_lower, (
            "parallel continuation must dispatch every task concurrently"
        )
        assert "isolated agent" in body_lower or "one agent per" in body_lower, (
            "parallel continuation must isolate each task in its own agent"
        )

    def test_parallel_write_tasks_require_checkout_isolation(self) -> None:
        body = _skill("cheese")
        body_lower = body.lower()
        assert "worktree_strategy" in body, (
            "parallel continuation must define how write tasks get separate checkouts"
        )
        assert "existing" in body_lower and "create" in body_lower and "harness" in body_lower, (
            "parallel continuation must support existing, create, and harness isolation"
        )
        assert "distinct" in body_lower and "worktree" in body_lower, (
            "parallel write tasks must require distinct worktrees"
        )
        assert "branch:" in body and "branch_from" in body, (
            "parallel write tasks must carry branch and branch_from metadata"
        )
        assert "same checkout" in body_lower or "shared checkout" in body_lower, (
            "cheese must explicitly refuse shared-checkout parallel writes"
        )


class TestWheypointParallelHandoff:
    def test_documents_parallel_continuation_schema(self) -> None:
        body = _skill("wheypoint")
        assert "mode: single" in body, (
            "wheypoint must document the default single-dispatch mode"
        )
        assert "mode: parallel" in body, (
            "wheypoint must document the parallel-dispatch mode"
        )
        assert "tasks:" in body, (
            "wheypoint must document the task list for parallel handoffs"
        )

    def test_documents_parallel_worktree_strategies(self) -> None:
        body = _skill("wheypoint")
        body_lower = body.lower()
        assert "worktree_strategy" in body, (
            "wheypoint must document portable worktree isolation strategy"
        )
        for strategy in ("existing", "create", "harness"):
            assert strategy in body_lower, (
                f"wheypoint must document `{strategy}` parallel isolation"
            )
        assert "worktree_root" in body, (
            "created worktrees need a documented root directory"
        )
        assert "branch:" in body and "branch_from" in body, (
            "parallel handoff examples must include branch metadata"
        )


# ---------------------------------------------------------------------------
# Wiring: install fallback list and README skill table
# ---------------------------------------------------------------------------


class TestInstallFallbackList:
    def test_includes_ultracook(self) -> None:
        install_sh = _read(REPO_ROOT / "scripts" / "install.sh")
        line = next(
            line
            for line in install_sh.splitlines()
            if line.startswith("EC_FALLBACK_SKILLS=")
        )
        assert "ultracook" in line, (
            "EC_FALLBACK_SKILLS must include ultracook so offline installs ship it"
        )


class TestReadmeMentionsUltracook:
    def test_skill_table_lists_ultracook(self) -> None:
        readme = _read(REPO_ROOT / "README.md")
        assert "skills/ultracook/SKILL.md" in readme
        assert "/ultracook" in readme


# ---------------------------------------------------------------------------
# Cross-skill integrity: phase reports keep their status/next contract
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("skill_name", ["age", "press", "cook", "cure"])
def test_phase_reports_name_status_and_next(skill_name: str) -> None:
    """Every phase that ultracook spawns must surface a status+next field
    so the orchestrator can decide whether to proceed, halt, or finish.
    """
    body = _skill(skill_name)
    assert "status:" in body, f"{skill_name} report must include a `status:` field"
    assert "next:" in body, f"{skill_name} report must include a `next:` field"


# ---------------------------------------------------------------------------
# Hardening pass — press additions
#
# These tests cover spec-mandated contracts that the initial cut left
# implicit: every handoff schema documents `artifact:` (not just status/next),
# the orchestrator must read the slug file rather than infer from stdout,
# the autonomous handoff option in mold must not be pre-selected, the
# existing-handoffs guard must enumerate all four phase paths, and press's
# readiness-to-status mapping must stay documented.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("skill_name", ["age", "press", "cook", "cure", "ultracook"])
def test_phase_handoff_documents_artifact_field(skill_name: str) -> None:
    """The spec's minimum handoff schema is four lines: status, next,
    artifact, orientation. The first parametrized test covers status+next;
    this one locks down `artifact:` so a future edit cannot silently shrink
    the schema and break the orchestrator's halt-and-surface contract.
    """
    body = _skill(skill_name)
    assert "artifact:" in body, (
        f"{skill_name} handoff schema must document the `artifact:` field"
    )


class TestUltracookReadsSlugFile:
    """The orchestrator MUST read the slug file after each sub-agent
    returns — inferring success from the sub-agent's last line of output
    silently bypasses the halt-and-surface contract.
    """

    def test_rule_present_in_skill_md(self) -> None:
        body = _skill("ultracook")
        # Acceptable phrasings: "read the file", "read each phase's
        # handoff slug", or any explicit instruction not to infer from
        # stdout. Match on the substantive prohibition.
        body_lower = body.lower()
        assert "read the file" in body_lower or "read the slug" in body_lower or (
            "read each phase" in body_lower and "handoff" in body_lower
        ), "ultracook must instruct the orchestrator to read the slug file"
        assert "stdout" in body_lower or "last line" in body_lower, (
            "ultracook must explicitly forbid inferring success from sub-agent stdout"
        )


class TestMoldHighBlastNotPreSelected:
    """Autonomous-pipeline opt-in is a deliberate user gate. Mold's
    high-blast-radius handoff must not pre-select /ultracook (or any other
    autonomous option) — the user must opt in explicitly."""

    def test_no_preselect_for_autonomous(self) -> None:
        body = _skill("mold")
        body_lower = body.lower()
        # Either explicit "never pre-select" wording, or "the user must opt
        # in" — both are sanctioned phrasings in the spec dialogue.
        assert "never pre-select" in body_lower or "must opt in" in body_lower, (
            "mold must spell out that autonomous options are not pre-selected"
        )


class TestUltracookExistingHandoffsScansAllPhases:
    """The existing-handoff guard must check every phase path that the
    orchestrator could have written. Missing one (e.g. only checking cook +
    age) would let a stale press / cure handoff sneak past the guard."""

    @pytest.mark.parametrize("phase", ["cook", "press", "age", "cure"])
    def test_each_phase_path_is_named_in_existing_guard(self, phase: str) -> None:
        body = _skill("ultracook")
        # The existing-handoffs section must mention every phase's handoff
        # path. Each phase appears in the chain table too, so we assert on
        # the dedicated guard section by requiring the path twice (table
        # row + guard description) — dropping it from one site would still
        # break the boundary contract.
        path = f".cheese/{phase}/"
        assert body.count(path) >= 2, (
            f"ultracook must reference {path}<slug>.md in both the chain "
            f"table and the existing-handoffs guard (count<2 means one site "
            f"silently shrank)"
        )


class TestPressReadinessMapsToStatus:
    """Press's readiness verdict must map to the handoff slug's status
    field — `blocked` and `follow-up recommended` are halt states that
    stop the autonomous chain. Losing the mapping line would let the
    orchestrator march past a non-green press."""

    def test_halt_states_named(self) -> None:
        body = _skill("press")
        # Both halt-flavoured readiness verdicts must still be named, and
        # the slug schema must mention `halt:` so the mapping is visible.
        assert "blocked" in body
        assert "follow-up recommended" in body
        assert "halt" in body, (
            "press must document how `blocked` / `follow-up recommended` "
            "translate to a halt status on the handoff slug"
        )

    def test_ready_for_age_maps_to_ok(self) -> None:
        body = _skill("press")
        # The success-side mapping (`ready for /age` → `status: ok`,
        # `next: age`) must also be visible so the orchestrator can chain
        # past press without guessing.
        assert "ready for /age" in body
        assert "next: age" in body or "next:" in body and "age" in body


class TestCheeseContinueScansNotes:
    """`/cheese --continue` must scan culture's notes slug too — culture is
    the only skill that can hand off to /mold, /cook, or /ultracook from a
    notes-only state, so dropping notes from the scan would silently break
    that resumption path."""

    def test_notes_slug_in_scan(self) -> None:
        body = _skill("cheese")
        # The scan-paths phrase must include `notes` alongside the four
        # implementation phases. Either an explicit list or a brace
        # expansion is acceptable.
        assert "notes" in body, (
            "cheese --continue must scan .cheese/notes/<slug>.md so culture "
            "handoffs (next: mold|cook|ultracook|stop) are picked up"
        )


# ---------------------------------------------------------------------------
# Cure pass — architectural fixes from /age findings #1, #2, #5
#
# Finding #1: each phase's --auto contract chains forward in-session, so
# without an explicit no-chain directive sub-agent #1 would run the entire
# pipeline and the per-phase fresh-context property would not be delivered.
# Finding #2: the chain ends at cure₂ but age's cap-enforcement requires a
# terminal age₃ that writes `next: done`.
# Finding #5: mold's high-blast branch must fire for `high` verdict only,
# not `medium or high` (per the user's literal mold-conversation text).
# ---------------------------------------------------------------------------


class TestUltracookNoChainDirective:
    """Ultracook's spawn prompt MUST explicitly disable the chain-forward
    behaviour each phase's --auto contract documents. Without the override,
    sub-agent #1 runs the whole pipeline inside its own context and the
    fresh-context-per-phase property is silently broken."""

    def test_prompt_template_disables_chaining(self) -> None:
        body = _skill("ultracook")
        body_lower = body.lower()
        # The override must be visible in the Agent() prompt template.
        # Acceptable phrasings: "do not chain forward", "this phase only",
        # "stop" + "do not invoke the next phase", or the equivalent.
        assert "do not chain forward" in body_lower or "this phase only" in body_lower, (
            "ultracook's spawn prompt must explicitly direct the sub-agent "
            "not to chain forward to the next phase"
        )

    def test_dedicated_no_chain_section_present(self) -> None:
        body = _skill("ultracook")
        # The contract is load-bearing enough to deserve its own section
        # so future contributors can find it from the table of contents.
        assert "no-chain" in body.lower() or "isolation directive" in body.lower(), (
            "ultracook must dedicate a section to the no-chain isolation "
            "directive — without it the per-phase isolation guarantee is "
            "easy to remove silently"
        )


@pytest.mark.parametrize("phase", ["cook", "press", "age", "cure"])
def test_phase_documents_ultracook_no_chain_override(phase: str) -> None:
    """Every phase ultracook spawns must explicitly document that, when
    invoked from ultracook with the no-chain directive, it writes its
    handoff slug and stops instead of chaining forward."""
    body = _skill(phase)
    assert "/ultracook" in body, (
        f"{phase} must mention /ultracook so the no-chain override is documented"
    )
    body_lower = body.lower()
    # Either an explicit section header, or the no-chain phrasing inline,
    # is acceptable. The point is that a contributor reading the auto-mode
    # contract sees the override.
    assert "from /ultracook" in body_lower or "no-chain" in body_lower or (
        "do not chain forward" in body_lower
    ), f"{phase}'s auto-mode section must document the ultracook no-chain override"


class TestUltracookChainTerminatesInAge:
    """The two-cure-pass cap is enforced inside `/age --auto` (it writes
    `next: done` once two cure passes have completed). For that cap to
    actually fire from ultracook's chain, the chain must terminate in a
    third age spawn — without it, the orchestrator stops at cure₂ before
    age can write the cap-enforcing handoff."""

    def test_chain_table_mentions_age3(self) -> None:
        body = _skill("ultracook")
        # The chain table or the surrounding prose must reference age₃ /
        # spawn #7 / a third age invocation, plus the spawn must write
        # `next: done` to terminate the chain.
        assert "age₃" in body or "spawn #7" in body or "third age" in body.lower() or (
            "seven spawns" in body.lower()
        ), "ultracook chain must include a terminating third age (age₃)"
        # The terminal age must write `next: done` so the orchestrator
        # stops rather than expecting a phantom eighth spawn.
        assert "next: done" in body
        # Counting `/age <slug> --auto` occurrences gives a structural
        # check independent of section wording: 3 ages in the chain table.
        assert body.count("/age <slug> --auto") >= 3, (
            "ultracook chain table must list at least three /age <slug> --auto "
            f"spawns; found {body.count('/age <slug> --auto')}"
        )


class TestUltracookCapEnforcedByChainLength:
    """Mechanism-B contract: the two-cure-pass cap is enforced by
    ultracook's fixed chain length, not by age tracking the pass count or
    by age₃ writing a special `next: done`. Fresh-context age cannot count
    prior cure passes — any contract requiring it to "see the cap reached"
    is non-functional. These tests lock the chosen mechanism in so a
    future edit cannot silently revert to the broken hybrid contract."""

    def test_ultracook_says_chain_length_enforces_cap(self) -> None:
        body = _skill("ultracook")
        body_lower = body.lower()
        # Mechanism-B signal: somewhere in ultracook's body, the cap must
        # be attributed to chain length / table length, not to age.
        assert "chain length" in body_lower or "table length" in body_lower or (
            "fixed chain" in body_lower
        ), "ultracook must declare that chain length (not age) enforces the cap"

    def test_ultracook_says_age_next_is_informational(self) -> None:
        body = _skill("ultracook")
        body_lower = body.lower()
        # Under mechanism B, age's `next:` is descriptive: it reports what
        # age observed, but doesn't drive cap enforcement. The contract
        # must spell that out so a future edit doesn't restore the
        # contradictory "age₃ writes the cap-enforcing next: done" claim.
        assert "informational" in body_lower or "informative" in body_lower, (
            "ultracook must spell out that age's next: field is informational, "
            "not load-bearing for cap enforcement"
        )

    def test_age_section_does_not_leak_chain_table_internals(self) -> None:
        body = _skill("age")
        # Encapsulation enforcement: age's section must not name specific
        # spawn numbers — those are orchestrator details that don't
        # belong in a phase's docs.
        for spawn in ("spawn #3", "spawn #5", "spawn #7"):
            assert spawn not in body, (
                f"age must not reference ultracook's specific {spawn} — "
                "use a generic rule that doesn't couple age's docs to the "
                "chain table's exact layout"
            )


class TestMoldHighBlastIsHighOnly:
    """The high-blast-radius handoff branch must fire for shape-check
    verdict `high` only — the user's literal mold-conversation text said
    'if it's a high blast radius', not 'medium or high'. Including medium
    is over-broad: a medium-verdict spec is still appropriate for the
    in-session `/cook --auto` chain."""

    def test_high_branch_says_high_only(self) -> None:
        body = _skill("mold")
        body_lower = body.lower()
        # The high-blast-radius branch heading or surrounding prose must
        # carry the "high only" qualifier so the scope is unambiguous.
        assert "high only" in body_lower or "verdict `high` only" in body, (
            "mold's high-blast branch must restrict to verdict `high` only, "
            "not `medium or high`"
        )

    def test_medium_keeps_standard_handoff(self) -> None:
        body = _skill("mold")
        # The low-branch heading must include `medium` so it's visible
        # that medium-verdict specs route through standard /cook handoff.
        # Either "low or medium" or "low and medium" is acceptable.
        assert "low or medium" in body.lower() or "low` or `medium`" in body, (
            "mold's standard handoff branch must explicitly include medium "
            "so the verdict routing is unambiguous"
        )


# ---------------------------------------------------------------------------
# wheypoint-next-contract-v2 — gated: status, research/think next: values,
# next: hold, missing-next:-is-malformed, the inline next: list + order:,
# and the derive-from-blockers authoring rule.
#
# The audit behind this spec found 17/69 slugs shipped a `next:` header that
# contradicted their own body, all carrying `status: ok`. These tests lock
# the five contract clauses that close that gap so a future edit cannot
# silently drop one and reopen the misfire. They assert on the prose
# contract in wheypoint (authoring schema) and cheese (--continue routing),
# and keep two regression guards proving the additive changes did not break
# the existing `status: ok` + pipeline `next:` path.
# ---------------------------------------------------------------------------


class TestWheypointGatedStatus:
    """`status:` must gain a third value, `gated:`, distinct from `ok` and
    `halt:`. It means work is fine but the next step is blocked on a human
    decision — the value that produces the stop-and-ask-direction path the
    audit found was missing."""

    def test_status_enum_lists_gated(self) -> None:
        body = _skill("wheypoint")
        # The header schema line must show all three status values.
        assert "status: ok | gated:" in body and "halt:" in body, (
            "wheypoint status: enum must read `ok | gated: <...> | halt: <...>`"
        )

    def test_gated_means_decision_not_auto_dispatch(self) -> None:
        body = _skill("wheypoint")
        body_lower = body.lower()
        assert "gated:" in body, "wheypoint must document the gated: status value"
        # gated: is defined as a human-decision gate, not an auto-dispatch.
        assert "decision" in body_lower, (
            "gated: must be defined as a blocked-on-human-decision state"
        )


class TestCheeseGatedRouting:
    """`/cheese --continue` must route `gated:` to an ask-direction prompt
    (research / decide / build) and dispatch nothing until the user picks —
    the explicit fix for the realized misfire (a binary design popup that
    presumed `decide`)."""

    def test_gated_branch_present(self) -> None:
        body = _skill("cheese")
        body_lower = body.lower()
        assert "gated:" in body, (
            "cheese --continue must document a gated: routing branch"
        )
        # The three directions the reader must offer.
        assert "research" in body_lower and "decide" in body_lower and "build" in body_lower, (
            "gated: branch must ask the user which direction: research / decide / build"
        )

    def test_gated_does_not_auto_dispatch(self) -> None:
        body = _skill("cheese")
        body_lower = body.lower()
        # The clause must forbid auto-dispatch and the presumptive popup.
        assert (
            "dispatch nothing" in body_lower or "do not auto-dispatch" in body_lower
        ), "gated: branch must dispatch nothing until the user picks a direction"


class TestWheypointReadonlyNextValues:
    """Single-value `next:` must accept `briesearch | culture`
    so 'just go research this' is expressible as a bare next:, and these
    auto-dispatch under status: ok (read-only, low-risk)."""

    def test_next_enum_lists_readonly_kickoffs(self) -> None:
        body = _skill("wheypoint")
        for value in ("briesearch", "culture"):
            assert value in body, (
                f"wheypoint next: enum must include the read-only kickoff `{value}`"
            )

    def test_readonly_values_documented_as_auto_dispatch(self) -> None:
        body = _skill("wheypoint")
        body_lower = body.lower()
        assert "read-only" in body_lower, (
            "wheypoint must mark briesearch/culture as read-only kickoffs"
        )


class TestCheeseReadonlyAutoDispatch:
    """`/cheese --continue` must auto-dispatch `next: briesearch|culture`
    when `status: ok` — frictionless research kickoff, not gated."""

    def test_readonly_kickoff_branch_present(self) -> None:
        body = _skill("cheese")
        body_lower = body.lower()
        for value in ("briesearch", "culture"):
            assert value in body, (
                f"cheese --continue must route the read-only kickoff `{value}`"
            )
        assert "auto-dispatch" in body_lower, (
            "read-only kickoffs must auto-dispatch under status: ok"
        )


class TestWheypointHoldAndMissingNext:
    """`next: hold` (restore orientation, wait, dispatch nothing) and the
    rule that a missing `next:` is malformed — authors must declare intent
    explicitly; `hold` is the value for 'no action'."""

    def test_next_enum_lists_hold(self) -> None:
        body = _skill("wheypoint")
        assert "hold" in body, "wheypoint next: enum must include `hold`"

    def test_hold_distinct_from_done(self) -> None:
        body = _skill("wheypoint")
        body_lower = body.lower()
        # hold must be defined as wait-for-instruction, distinct from done.
        assert "hold" in body and "done" in body_lower, (
            "wheypoint must distinguish hold (wait) from done (finished)"
        )

    def test_missing_next_is_malformed(self) -> None:
        body = _skill("wheypoint")
        body_lower = body.lower()
        assert "malformed" in body_lower, (
            "wheypoint must state a missing next: is a malformed handoff"
        )


class TestCheeseHoldAndMissingNext:
    """`/cheese --continue` must treat `next: hold` as terminal-surface
    (orientation, no dispatch) and a missing `next:` as malformed (flag,
    no guess, no defaulting to a phase)."""

    def test_hold_is_surface_no_dispatch(self) -> None:
        body = _skill("cheese")
        body_lower = body.lower()
        assert "hold" in body, "cheese --continue must route next: hold"
        # hold surfaces orientation and stops without dispatching.
        assert "without dispatching" in body_lower or "stop without dispatch" in body_lower or (
            "hold" in body_lower and "wait" in body_lower
        ), "next: hold must surface orientation and stop without dispatching"

    def test_missing_next_flagged_not_guessed(self) -> None:
        body = _skill("cheese")
        body_lower = body.lower()
        assert "malformed handoff: next: required" in body, (
            "cheese --continue must flag a missing next: with the exact message"
        )
        # It must refuse to guess or default to a phase.
        assert "do not guess a next step" in body_lower, (
            "missing next: must be flagged, not guessed or defaulted"
        )


class TestWheypointNextListForm:
    """Multi-value `next:` list form with a required `order:` — kicks off
    several read-only follow-ups from one handoff. Restricted to read-only
    skills; parallel writes still need the heavy mode: parallel + tasks:."""

    def test_list_form_documented(self) -> None:
        body = _skill("wheypoint")
        # The bracketed list shape and the required order: key.
        assert "next: [" in body, (
            "wheypoint must document the inline next: list form `next: [<skill> \"<arg>\", ...]`"
        )
        assert "order:" in body, "next: list form must document the order: key"
        assert "order: parallel" in body and "order: sequential" in body, (
            "next: list must document both parallel and sequential order"
        )

    def test_order_required_for_list(self) -> None:
        body = _skill("wheypoint")
        body_lower = body.lower()
        assert "required" in body_lower and "order:" in body, (
            "order: must be documented as required when next: is a list"
        )

    def test_list_restricted_to_readonly(self) -> None:
        body = _skill("wheypoint")
        body_lower = body.lower()
        # The inline list must be restricted to read-only skills, with the
        # heavy tasks: block named as the path for parallel writes.
        assert "read-only" in body_lower, (
            "wheypoint must restrict the inline next: list to read-only skills"
        )
        assert "tasks:" in body, (
            "wheypoint must point parallel writes at the heavy mode: parallel + tasks: block"
        )


class TestCheeseNextListRouting:
    """`/cheese --continue` must parse a `next:` list with required
    `order:`, dispatch parallel (concurrent read agents) or sequential, and
    reject non-read-only skills with a pointer to the heavy tasks: block."""

    def test_list_branch_present(self) -> None:
        body = _skill("cheese")
        body_lower = body.lower()
        assert "next:" in body and "list" in body_lower, (
            "cheese --continue must document a next:-is-a-list branch"
        )
        assert "order:" in body, "list branch must parse the order: key"

    def test_order_required_else_stop(self) -> None:
        body = _skill("cheese")
        body_lower = body.lower()
        # order: missing -> stop and ask for a corrected handoff.
        assert "order:" in body and "required" in body_lower, (
            "list branch must treat order: as required"
        )

    def test_parallel_and_sequential_dispatch(self) -> None:
        body = _skill("cheese")
        body_lower = body.lower()
        assert "order: parallel" in body and "order: sequential" in body, (
            "list branch must handle both order: parallel and order: sequential"
        )
        # Parallel fans out concurrent read agents in the same turn.
        assert "concurrent" in body_lower or "same turn" in body_lower, (
            "order: parallel must dispatch concurrent read agents in the same turn"
        )

    def test_rejects_write_skills_in_inline_list(self) -> None:
        body = _skill("cheese")
        body_lower = body.lower()
        # A write/pipeline skill in the inline list must be rejected and
        # routed to the heavy tasks: block (which carries write isolation).
        assert "reject" in body_lower, (
            "inline list must reject write/pipeline skills"
        )
        assert "tasks:" in body, (
            "rejection must point at the heavyweight mode: parallel + tasks: block"
        )


class TestWheypointDeriveNextFromBlockers:
    """The root-cause authoring rule: read the body's Open-questions/blockers
    section before writing the header, and derive next: from the blockers,
    not optimism. An unresolved blocker means status: gated:, never ok + a
    bare actionable next:. The Suggested-skills map must wire session states
    to the new values."""

    def test_derive_from_blockers_rule_present(self) -> None:
        body = _skill("wheypoint")
        body_lower = body.lower()
        # Must instruct reading the blockers section before authoring next:.
        assert "open questions and blockers" in body_lower or "blockers" in body_lower, (
            "wheypoint must tell the author to read the Open-questions/blockers section"
        )
        # The derive-from-blockers-not-optimism rule.
        assert "optimism" in body_lower or "derive" in body_lower, (
            "wheypoint must state next: derives from blockers, not optimism"
        )

    def test_blocker_means_gated_not_ok(self) -> None:
        body = _skill("wheypoint")
        body_lower = body.lower()
        # An unresolved blocker must force gated:, never ok + bare next:.
        assert "gated:" in body and ("never" in body_lower), (
            "wheypoint must state an unresolved blocker is gated:, never status: ok "
            "plus a bare actionable next:"
        )

    @pytest.mark.parametrize(
        "state_value",
        [
            "briesearch",  # research wanted
            "gated:",      # decision pending
            "hold",        # compacting / no action
        ],
    )
    def test_suggested_skills_map_includes_new_values(self, state_value: str) -> None:
        body = _skill("wheypoint")
        assert state_value in body, (
            f"wheypoint Suggested-skills map must wire a session state to `{state_value}`"
        )


class TestNextContractV2BackwardCompatible:
    """Regression guards: the v2 changes are additive. An existing slug
    (status: ok + a pipeline next:, no mode:) and an existing mode: parallel
    + tasks: slug must both still route exactly as before."""

    def test_status_ok_pipeline_phase_still_routes(self) -> None:
        body = _skill("cheese")
        # The original status: ok + pipeline-phase branch must survive,
        # listing the canonical pipeline phases.
        assert "status:" in body and "is `ok`" in body, (
            "cheese --continue must keep the status: ok dispatch branch"
        )
        for phase in ("mold", "cook", "press", "age", "cure", "affinage"):
            assert phase in body, (
                f"status: ok pipeline branch must still name the `{phase}` phase"
            )

    def test_mode_parallel_tasks_still_documented(self) -> None:
        body = _skill("cheese")
        # The heavyweight write-isolation path must be untouched.
        assert "mode: parallel" in body and "tasks:" in body, (
            "the heavyweight mode: parallel + tasks: path must remain documented"
        )
        assert "worktree_strategy" in body, (
            "parallel write-isolation strategy must remain documented"
        )
