"""Documentation-lint tests for the ultracook orchestrator and the SKILL.md
changes the ultracook spec requires across the phase chain.

These tests treat each `SKILL.md` as a contract document: they assert that
handoff schemas, typed phase-agent routing, the `--continue` flag on
`/cheese`, and related orchestration clauses stay written down.

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
    TABLE_HEADER = "## Phases and artifact ownership"

    def test_lists_seven_phases_in_order(self) -> None:
        body = _skill("ultracook")
        # Anchor to the chain-table section so unrelated prose cannot satisfy
        # the ordering check. The seventh spawn proves terminal publishability.
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


class TestUltracookTypedAgentContract:
    def test_assigns_specialists_by_phase(self) -> None:
        body = _skill("ultracook").lower()
        for role in ("planner", "coder", "reviewer"):
            assert role in body
        assert "harvest" in body and "parent" in body
        assert "plate" in body and "parent" in body

    def test_uses_shared_resolver(self) -> None:
        body = _skill("ultracook")
        assert "../cheese/references/agent-resolution.md" in body
        assert "minimum power" in body.lower()


class TestUltracookHandoffContract:
    def test_uses_versioned_runtime_transaction(self) -> None:
        body = _skill("ultracook")
        assert "handoff-commit" in body
        assert "handoff-resolve" in body
        assert ".cheese/<phase>/<work-id>/<operation-id>-<slug>.md" in body
        assert "flat slug file" in body

    def test_resolver_actions_are_explicit(self) -> None:
        body = _skill("ultracook")
        for action in ("halt", "done", "dispatch", "hold", "tasks", "unavailable"):
            assert action in body


class TestPhaseHandoffContract:
    @pytest.mark.parametrize("skill_name", ["cook", "cure"])
    def test_phase_commits_and_resolves_versioned_handoff(self, skill_name: str) -> None:
        body = _skill(skill_name)
        assert "handoff-commit" in body
        assert "handoff-resolve" in body
        assert "WorkRecord" in body


class TestCultureCheckpoint:
    def test_delegates_checkpoint_schema_to_wheypoint(self) -> None:
        body = _skill("culture")
        assert "/wheypoint" in body
        assert "versioned" in body
        assert "WorkRecord" in body

    def test_still_forbids_production_writes(self) -> None:
        body = _skill("culture").lower()
        assert "production code" in body
        assert "does not commit" in body
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
# /mold — low/medium-blast-radius handoff offers a non-recommended /ultracook
# ---------------------------------------------------------------------------


def _mold_low_medium_handoff_menu() -> str:
    """The option list under mold's non-decomposable low/medium handoff branch.

    Sliced from the branch header to the section's closing rationale paragraph
    so assertions target the menu options themselves, not the surrounding
    prose (which also references /ultracook and /cook --auto).
    """
    body = _skill("mold")
    start = body.index("**Non-decomposable, low- or medium-blast-radius specs")
    end = body.index("`/cook --auto` is omitted", start)
    return body[start:end]


class TestMoldLowMediumHandoff:
    def test_offers_ultracook_option(self) -> None:
        # /ultracook already appears in the high-blast-radius branch, so the
        # body-wide TestMoldHighBlastHandoff guard cannot catch removal of this
        # low/medium menu option — assert it on the branch's own option list.
        menu = _mold_low_medium_handoff_menu()
        assert "/ultracook <spec-path>" in menu, (
            "mold's low/medium handoff menu must offer the /ultracook option"
        )

    def test_states_fast_path_cost(self) -> None:
        # Acceptance: the option states the 1-curd fast-path (linear chain, no
        # decomposer spawn) so users are not deterred by parallel-mode overhead.
        menu = _mold_low_medium_handoff_menu()
        assert "fast-path" in menu and "decomposer" in menu, (
            "the /ultracook option must state the fast-path with no decomposer spawn"
        )

    def test_cook_keeps_recommended_slot(self) -> None:
        # Menu-addition, not recommendation-flip: /cook stays recommended
        # (the flip was the explicitly rejected direction).
        menu = _mold_low_medium_handoff_menu()
        recommended = [ln for ln in menu.splitlines() if "*(recommended)*" in ln]
        assert len(recommended) == 1, (
            "the low/medium menu must mark exactly one recommended option"
        )
        assert "/cook <spec-path>" in recommended[0], (
            "/cook must remain the recommended low/medium option"
        )
        assert "/ultracook" not in recommended[0], (
            "the /ultracook option must stay non-recommended"
        )


# ---------------------------------------------------------------------------
# /cheese — --continue <slug> flag for fresh-context resumption
# ---------------------------------------------------------------------------


class TestCheeseContinueFlag:
    def test_documents_workrecord_continuation(self) -> None:
        body = _skill("cheese")
        assert "--continue" in body
        assert "work continue" in body
        assert "WorkRecord" in body
        assert "modification time" in body

    def test_legacy_notes_are_explicit_migration_input(self) -> None:
        body = _skill("cheese")
        assert "work migrate" in body
        assert "legacy" in body.lower()

    def test_reserved_destinations_are_not_dispatched_as_phases(self) -> None:
        body = _skill("cheese")
        for destination in ("done", "hold", "tasks"):
            assert destination in body
        assert "never constructs or dispatches a phase command" in body
        assert "never a phase command" in body


class TestWheypointVersionedHandoff:
    def test_commits_one_versioned_checkpoint(self) -> None:
        body = _skill("wheypoint")
        assert "phase: wheypoint" in body
        assert "handoff-commit" in body
        assert ".cheese/wheypoint/<work-id>/<operation-id>-<slug>.md" in body

    def test_split_uses_ordered_task_directives(self) -> None:
        body = _skill("wheypoint")
        assert "next_phase: tasks" in body
        assert "payload.tasks" in body
        for field in ("phase", "subject", "input"):
            assert field in body

    def test_provenance_records_exact_inputs(self) -> None:
        body = _skill("wheypoint")
        for value in ("session identity", "branch and commit", "UTC timestamp", "parent artifact paths", "baseline"):
            assert value in body
        assert "Never accept user-supplied provenance" in body

    def test_join_uses_exact_parent_artifacts(self) -> None:
        body = _skill("wheypoint")
        assert "--join <artifact-a> <artifact-b>" in body
        assert "provenance.parents" in body
        assert "modification time" in body

    def test_split_is_one_persisted_handoff(self) -> None:
        body = _skill("wheypoint")
        assert "--split" in body
        assert "one wheypoint envelope" in body
        assert "action: tasks" in body


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
# Cross-skill integrity: phase reports use versioned runtime transactions.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("skill_name", ["age", "press", "cook", "cure"])
def test_phase_reports_use_versioned_destination_contract(skill_name: str) -> None:
    body = _skill(skill_name)
    assert "status: ok" in body, f"{skill_name} must document successful status"
    assert "next_phase" in body, f"{skill_name} must document its destination"
    assert "handoff-commit" in body, f"{skill_name} must commit through the runtime"


@pytest.mark.parametrize("skill_name", ["age", "press", "cook", "cure", "ultracook"])
def test_phase_handoff_uses_runtime_artifact_path(skill_name: str) -> None:
    body = _skill(skill_name)
    assert "artifact path" in body or "artifact returned" in body or "artifact returned by" in body
    assert "handoff-commit" in body


class TestUltracookReadsCommittedArtifact:
    def test_rule_present_in_skill_md(self) -> None:
        body = _skill("ultracook").lower()
        assert "runtime-returned" in body or "returned artifact path" in body
        assert "handoff-resolve" in body
        assert "stdout" in body


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


class TestUltracookExistingWorkGuard:
    def test_guard_uses_workrecord_not_flat_phase_scan(self) -> None:
        body = _skill("ultracook")
        assert "## Existing work" in body
        assert "WorkRecord" in body
        assert "/cheese --continue" in body
        assert "do not scan four flat paths" in body


class TestPressReadinessMapsToStatus:
    def test_blocked_maps_to_halt(self) -> None:
        body = _skill("press")
        assert "blocked" in body
        assert "status: halt" in body
        assert "non-empty reason" in body

    def test_ready_for_age_maps_to_ok(self) -> None:
        body = _skill("press")
        assert "ready for /age" in body
        assert "status: ok" in body
        assert "next_phase: age" in body


class TestCheeseContinuationAuthority:
    def test_workrecord_not_notes_scan(self) -> None:
        body = _skill("cheese")
        assert "WorkRecord" in body
        assert "work continue" in body
        assert "scan `.cheese/notes/`" not in body


# ---------------------------------------------------------------------------
# Cure pass: fresh phases do not chain, and the terminal age is preserved.
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
        # The contract is critical enough to deserve its own section so
        # future contributors can find it from the table of contents.
        assert "no-chain" in body.lower() or "isolation directive" in body.lower(), (
            "ultracook must dedicate a section to the no-chain isolation "
            "directive — without it the per-phase isolation guarantee is "
            "easy to remove silently"
        )


@pytest.mark.parametrize("phase", ["cook", "press", "age", "cure"])
def test_phase_documents_orchestrator_no_chain_override(phase: str) -> None:
    body = _skill(phase).lower()
    assert "fan pathway" in body or "/ultracook" in body
    assert "stop" in body
    assert "handoff-commit" in body


class TestUltracookChainTerminatesInAge:
    """The fixed chain must include the final age that proves publishability."""

    def test_chain_table_mentions_age3(self) -> None:
        body = _skill("ultracook")
        assert "age₃" in body or "spawn #7" in body or "third age" in body.lower() or (
            "seven spawns" in body.lower()
        ), "ultracook chain must include a terminating third age"
        assert "handoff-resolve" in body and "only `done` is publishable" in body
        assert body.count("/age <slug> --auto") >= 3, (
            "ultracook chain table must list at least three /age <slug> --auto "
            f"spawns; found {body.count('/age <slug> --auto')}"
        )


class TestUltracookCapEnforcedByChainLength:
    """The two-cure-pass cap belongs to ultracook's fixed chain."""

    def test_ultracook_says_chain_length_enforces_cap(self) -> None:
        body = _skill("ultracook")
        body_lower = body.lower()
        assert "chain length" in body_lower or "table length" in body_lower or (
            "fixed chain" in body_lower
        ), "ultracook must declare that chain length enforces the cap"

    def test_ultracook_routes_from_resolved_envelopes(self) -> None:
        body = _skill("ultracook")
        assert "handoff-resolve" in body
        assert "exact runtime-returned artifact path" in body
        assert "locate an artifact by slug" in body

    def test_age_section_does_not_leak_chain_table_internals(self) -> None:
        body = _skill("age")
        for spawn in ("spawn #3", "spawn #5", "spawn #7"):
            assert spawn not in body, (
                f"age must not reference ultracook's specific {spawn}; "
                "the orchestrator owns the chain position"
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


class TestWheypointHaltStatus:
    def test_human_decision_is_structured_halt(self) -> None:
        body = _skill("wheypoint")
        assert "status: halt" in body
        assert "halt_reason" in body
        assert "next_phase: hold" in body
        assert "does not dispatch" in body


class TestCheeseResolverRouting:
    def test_halt_does_not_dispatch(self) -> None:
        body = _skill("cheese")
        assert "halt" in body
        assert "never auto-dispatches" in body or "does not auto-dispatch" in body

    def test_available_and_unavailable_destinations_are_distinct(self) -> None:
        body = _skill("cheese")
        assert "available" in body
        assert "unavailable" in body
        assert "retain it" in body


class TestWheypointDestinations:
    def test_declared_destinations_are_registered_values(self) -> None:
        body = _skill("wheypoint")
        for value in ("mold", "cook", "press", "age", "cure", "affinage", "briesearch", "culture", "done", "hold", "tasks"):
            assert value in body

    def test_hold_and_done_are_distinct(self) -> None:
        body = _skill("wheypoint")
        assert "paused" in body
        assert "terminal" in body

    def test_missing_destination_is_rejected_by_runtime(self) -> None:
        body = _skill("wheypoint")
        assert "phase-owned declaration" in body
        assert "handoff-commit" in body


class TestTaskContinuation:
    def test_wheypoint_documents_ordered_directives(self) -> None:
        body = _skill("wheypoint")
        assert "non-empty ordered list" in body
        assert "{phase, subject, input?}" in body

    def test_cheese_uses_persisted_task_directives(self) -> None:
        body = _skill("cheese")
        assert "structured pending directives" in body
        assert "never a phase command" in body


class TestWheypointDeriveDestinationFromBlockers:
    def test_derive_from_blockers_rule_present(self) -> None:
        body = _skill("wheypoint").lower()
        assert "blockers" in body
        assert "optimism" in body

    def test_blocker_means_halt_and_hold(self) -> None:
        body = _skill("wheypoint")
        assert "status: halt" in body
        assert "next_phase: hold" in body


class TestUltracookDeterministicPhaseLoop:
    def test_handoff_resolver_referenced(self) -> None:
        body = _skill("ultracook")
        assert "handoff-resolve" in body
        assert "read_handoff_slug" not in body

    def test_runtime_path_is_authoritative(self) -> None:
        body = _skill("ultracook")
        assert "exact artifact path" in body or "returned artifact path" in body
        assert "flat" in body


# ---------------------------------------------------------------------------
# merge-cheese-factory-into-ultracook — parallel mode contract
#
# /cheese-factory folded into /ultracook as a second mode. These lock the
# parallel-mode contract clauses so a future edit cannot silently drop the
# mode gate, typed agent resolution, worktree lifecycle, milknado parity,
# recovery paths, terminal age gate, or resolution provenance.
# ---------------------------------------------------------------------------


class TestUltracookModeGate:
    """The decomposer is the authoritative mode gate; the single canonical
    PARALLEL_THRESHOLD (2) picks linear vs parallel."""

    def test_mode_selection_section_present(self) -> None:
        body = _skill("ultracook")
        assert "Mode selection" in body, (
            "ultracook must document a mode-selection gate"
        )
        assert "decomposer" in body.lower(), "the decomposer is the mode gate"

    def test_mode_selector_and_threshold_referenced(self) -> None:
        body = _skill("ultracook")
        assert "PARALLEL_THRESHOLD" in body, (
            "ultracook must name the canonical PARALLEL_THRESHOLD constant"
        )
        # The mode subcommand picks linear|parallel deterministically.
        assert "ultracook.pyz mode" in body or "pyz mode --count" in body, (
            "ultracook must invoke the deterministic mode selector"
        )

    def test_two_or_more_curds_is_parallel(self) -> None:
        body = _skill("ultracook")
        body_lower = body.lower()
        assert "2 or more" in body_lower or "2+" in body, (
            "ultracook must state 2+ curds routes to parallel mode"
        )
        assert "1-curd spec runs" in body and "linear mode" in body_lower, (
            "ultracook must state a 1-curd spec stays linear"
        )

    def test_fast_path_skips_decomposer_for_single_low_or_medium_blast_curd(self) -> None:
        body = _skill("ultracook")
        body_lower = body.lower()
        assert "fast-path" in body_lower, (
            "ultracook must document a deterministic fast-path before the decompose step"
        )
        assert "hint = 1" in body, (
            "fast-path must gate on a curd-count hint of exactly 1"
        )
        assert "low or medium" in body_lower, (
            "fast-path must require blast radius low or medium"
        )
        assert "skip the decomposer spawn" in body_lower, (
            "fast-path must skip the decomposer spawn entirely, not just prefer linear"
        )
        assert "never to pick parallel" in body_lower, (
            "the hint must be trusted only to skip work, never to choose parallel"
        )


class TestUltracookParallelTopology:
    """Parallel mode uses typed fresh-context phase agents in one curd worktree,
    then repeats review and final age over the merged diff."""

    def test_parallel_mode_section_present(self) -> None:
        body = _skill("ultracook")
        assert "## Parallel mode" in body

    def test_per_curd_pipeline_documented(self) -> None:
        body = _skill("ultracook")
        # Per-curd pipeline uses the parallel-curd phase table.
        assert "parallel-curd" in body, (
            "parallel mode must run each curd on the parallel-curd phase table"
        )

    def test_post_merge_final_age_documented(self) -> None:
        body = _skill("ultracook")
        body_lower = body.lower()
        assert "parallel-postmerge" in body, (
            "parallel mode must use the parallel-postmerge table"
        )
        assert "reviewer(final age)" in body_lower
        assert "post-merge" in body_lower or "merged diff" in body_lower


class TestUltracookWorktreeLifecycle:
    """The worktree helper harvests a curd branch with no fetch and tears the
    worktree + branch down afterward — no leaks (acceptance #5)."""

    def test_harvest_no_fetch(self) -> None:
        body = _skill("ultracook")
        body_lower = body.lower()
        assert "worktree harvest" in body, "parallel mode must harvest curd branches"
        assert "no `git fetch`" in body or "no git fetch" in body_lower or (
            "shared" in body_lower and "object store" in body_lower
        ), "harvest must state it needs no git fetch (shared object store)"

    def test_teardown_leaves_no_leak(self) -> None:
        body = _skill("ultracook")
        body_lower = body.lower()
        assert "worktree teardown" in body, "parallel mode must tear worktrees down"
        assert "leak" in body_lower, (
            "the teardown contract must state no worktree/branch leaks"
        )
        assert "worktree-agent-" in body or ".claude/worktrees/agent-" in body, (
            "teardown must name the worktree/branch pattern that must not leak"
        )


class TestUltracookMilknadoSeam:
    """milknado.probe() returns engine/tracker/none; parallel mode runs with
    milknado absent (native fan-out), and the self-verify vs verify-until-green
    parity is stated (acceptance #4)."""

    def test_three_probe_roles_documented(self) -> None:
        body = _skill("ultracook")
        body_lower = body.lower()
        assert "engine" in body_lower and "tracker" in body_lower, (
            "the milknado seam must name the engine and tracker roles"
        )
        assert "ultracook.pyz milknado" in body, (
            "ultracook must invoke the deterministic milknado probe"
        )

    def test_native_path_runs_without_milknado(self) -> None:
        body = _skill("ultracook")
        body_lower = body.lower()
        assert "native fan-out" in body_lower, (
            "parallel mode must document the native fan-out path when milknado is absent"
        )

    def test_parity_difference_stated(self) -> None:
        body = _skill("ultracook")
        body_lower = body.lower()
        # The intentional parity difference must be explicit.
        assert "self-verify" in body_lower, (
            "native curds must be documented as self-verifying (gates in-worker)"
        )
        assert "verify-until-green" in body_lower, (
            "milknado's verify-until-green must be named as the parity difference"
        )


class TestUltracookAgentResolution:
    """Ultracook resolves typed roles through the shared minimum-power protocol."""

    def test_shared_resolution_protocol_documented(self) -> None:
        body = _skill("ultracook").lower()
        assert "agent-resolution.md" in body
        assert "minimum capable power" in body
        assert "agent_resolution" in body

    def test_typed_phase_roles_documented(self) -> None:
        body = _skill("ultracook").lower()
        assert "planner/general" in body
        assert "coder(cook)" in body
        assert "reviewer(age)" in body
        assert "parent ownership for harvest and plate" in body

    def test_terminal_age_gate_documented(self) -> None:
        body = _skill("ultracook").lower()
        assert "terminal age is publishable only when the resolver returns `done`" in body
        assert "dispatch back to cure or a missing/malformed result halts" in body


class TestUltracookRecoveryPaths:
    """Parallel mode surfaces a worker-exhaustion recovery path and an
    aggregate-gate failure path (issue #194, acceptance #7)."""

    def test_worker_exhaustion_recovery(self) -> None:
        body = _skill("ultracook")
        body_lower = body.lower()
        assert "#194" in body or "194" in body, (
            "ultracook must cite issue #194 for the recovery paths"
        )
        assert "exhaust" in body_lower and "retry" in body_lower, (
            "parallel mode must document worker-exhaustion recovery (retry once)"
        )

    def test_aggregate_gate_failure_distinguishes_conflict_from_drift(self) -> None:
        body = _skill("ultracook")
        body_lower = body.lower()
        assert "aggregate" in body_lower, (
            "parallel mode must document the aggregate-gate failure path"
        )
        assert "cross-curd conflict" in body_lower or "cross-curd" in body_lower, (
            "aggregate-gate handling must distinguish a real cross-curd conflict"
        )
        assert "drift" in body_lower, (
            "aggregate-gate handling must distinguish harmless drift from a conflict"
        )


class TestUltracookOutputContract:
    """Behavioural output stays stable while resolution provenance exposes topology."""

    def test_output_contract_accounts_for_resolution_provenance(self) -> None:
        body = _skill("ultracook").lower()
        assert "behavioral output" in body
        assert "resolution provenance" in body
        assert "topology" in body


class TestUltracookResume:
    """--resume brings ultracook up to spec with the retired cheese-factory:
    the Inputs list advertises it, the Topology advances the manifest at every
    phase boundary, and a dedicated section drives the resume flow."""

    def test_inputs_list_resume_flag(self) -> None:
        body = _skill("ultracook")
        assert "`--resume <slug>`" in body, (
            "Inputs must advertise the --resume <slug> flag"
        )

    def test_topology_advances_manifest_at_phase_boundaries(self) -> None:
        body = _skill("ultracook")
        # Every schema phase past the decomposer scaffold must be emitted by a
        # manifest_update set-phase call threaded into the topology prose.
        for phase in (
            "seed_complete",
            "curds_complete",
            "merge_complete",
            "wiring_complete",
            "final_merge_complete",
            "post_review_complete",
            "pr_publish_complete",
        ):
            assert f"set-phase --manifest <path> --phase {phase}" in body or (
                f"--phase {phase}" in body and "manifest_update set-phase" in body
            ), f"topology must advance the manifest to {phase}"
        assert "manifest_update set-curd-status" in body, (
            "per-curd status must be recorded via set-curd-status"
        )
        assert "manifest_update set-wiring-status" in body, (
            "per-wiring status must be recorded via set-wiring-status"
        )

    def test_resume_section_present(self) -> None:
        body = _skill("ultracook")
        assert "## --resume <slug>" in body, "a dedicated --resume section must exist"
        assert "git cat-file -e" in body, (
            "resume must verify recorded commit SHAs still exist (rebase guard)"
        )
        assert "phase_summary" in body and "carry_forward" in body, (
            "resume must read phase_summary/carry_forward for cross-seam continuity"
        )

    def test_phase_strings_agree_across_writer_reader_and_schema(self) -> None:
        # The whole point of --resume: a phase string written by the Topology
        # writer prose must round-trip through the reader section and the
        # schema enum. Drift in any one of the three (edit one place, forget
        # the others) silently breaks resume and validate_skills won't catch it.
        import json
        import re

        body = _skill("ultracook")
        schema_path = SKILLS_DIR / "ultracook" / "references" / "manifest-schema.json"
        schema_enum = json.loads(_read(schema_path))["properties"]["phase"]["enum"]

        # Reader: the ordered arrow-joined enum inside the `## --resume` section.
        resume_section = body.split("\n## --resume <slug>", 1)[1]
        arrow_span = re.search(r"`([a-z_]+(?: → [a-z_]+)+)`", resume_section)
        assert arrow_span, "resume section must list the ordered phase enum"
        reader_enum = [p.strip() for p in arrow_span.group(1).split("→")]

        # Writer: every `--phase <X>` the Topology prose (before the reader
        # section) tells the orchestrator to set.
        topology = body.split("\n## --resume <slug>", 1)[0]
        writer_phases = set(re.findall(r"--phase ([a-z_]+)", topology))

        assert reader_enum == schema_enum, (
            "reader arrow-list must match the schema phase enum exactly (order + members)"
        )
        assert writer_phases == set(schema_enum) - {"gate_approved"}, (
            "Topology must write every schema phase past the decomposer scaffold "
            f"(gate_approved); writer={sorted(writer_phases)} schema={schema_enum}"
        )
