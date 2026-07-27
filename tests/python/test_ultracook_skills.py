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


class TestUltracookResolvesToCook:
    """PR1 acceptance criterion (subagent-routing-overhaul.md): '/ultracook
    invocation resolves to /cook'. Locks the literal redirect claim in both
    the retirement stub and /cheese's routing table — a future edit could
    silently drop either half without any other test noticing."""

    def test_frontmatter_description_states_the_redirect(self) -> None:
        body = _skill("ultracook")
        assert "Any /ultracook invocation resolves to /cook" in body

    def test_redirect_section_documents_flag_passthrough(self) -> None:
        body = _skill("ultracook")
        redirect_idx = body.find("## Redirect")
        assert redirect_idx != -1, "ultracook must document a `## Redirect` section"
        redirect_section = body[redirect_idx:]
        assert (
            "Any `/ultracook <spec> [flags]` invocation resolves to `/cook <spec> [flags]`"
            in redirect_section
        )
        for flag in ("--open-pr", "--resume <slug>", "--auto"):
            assert flag in redirect_section, f"redirect section missing `{flag}` passthrough"

    def test_cheese_routing_table_mirrors_the_redirect(self) -> None:
        body = _skill("cheese")
        assert "`/ultracook <slug-or-path>` resolves to `/cook <slug-or-path>`" in body

    def test_retained_legacy_manifest_template_belongs_to_cook_internals(self) -> None:
        stub = _skill("ultracook")
        prompt = _read(SKILLS_DIR / "ultracook" / "references" / "decomposer-prompt.md")

        assert "remain at their existing paths" in stub
        assert "remain in place, untouched" not in stub
        assert "retained legacy-manifest template" in prompt
        assert "consumed by `/cook`'s fan-path internals" in prompt
        assert "Loaded by `/ultracook` at Phase 0" not in prompt
        assert "decomposer sub-agent for /ultracook" not in prompt


class TestUltracookPhaseChain:
    """/ultracook's linear-mode mechanics (single, un-decomposed spec) now
    live in /cook's own `## Auto mode` chain; its parallel-mode mechanics
    (decomposed spec) live in /cook's `## Fan pathway` two-table topology.
    There is no longer one literal 7-spawn table — the topology genuinely
    changed shape when ultracook retired — so these assertions anchor to
    /cook's actual chain descriptions instead of forcing the old table
    format to reappear."""

    def test_lists_seven_phases_in_order(self) -> None:
        body = _skill("cook")
        # Single-coder auto chain: press -> age -> cure -> scoped re-verify
        # age, capped at two cure passes, terminal next: done.
        auto_idx = body.find("## Auto mode")
        assert auto_idx != -1, "cook must document `## Auto mode`"
        auto_section = body[auto_idx:]
        cursor = 0
        for invocation in (
            "/press <slug> --auto",
            "/age <slug> --auto",
            "/cure --auto --stake medium+",
            "/age --scope <touched-paths> --auto",
        ):
            next_idx = auto_section.find(invocation, cursor)
            assert next_idx != -1, (
                f"cook's Auto mode chain missing `{invocation}` after position {cursor}"
            )
            cursor = next_idx + 1
        assert "two cure passes" in auto_section.lower()
        # Fan pathway: the two-table wave-fan topology (per-curd, post-merge).
        fan_idx = body.find("## Fan pathway")
        assert fan_idx != -1, "cook must document `## Fan pathway`"
        fan_section = body[fan_idx:]
        assert "coder(cook) → coder(press) → reviewer(age) → coder(cure) → reviewer(final age)" in fan_section
        assert "press → age → cure → age" in fan_section

    def test_propagates_auto_through_every_phase(self) -> None:
        body = _skill("cook")
        for invocation in (
            "/press <slug> --auto",
            "/age <slug> --auto",
            "/cure --auto --stake medium+",
        ):
            assert invocation in body, f"missing `{invocation}` in cook's auto chain"
        # Cure floor must be medium+ to match /cook --auto's contract.
        assert "medium+" in body
        # --auto propagates throughout both the single-coder chain and the
        # fan pathway's own dispatches — a broad floor, not a spawn-count.
        assert body.count("--auto") >= 7, (
            f"expected --auto >=7 occurrences across cook's chains; got {body.count('--auto')}"
        )


class TestUltracookTypedAgentContract:
    """Typed-role resolution now lives in /cook's own Resolution-provenance
    section (its Fan pathway absorbed /ultracook's mechanics)."""

    def test_assigns_specialists_by_phase(self) -> None:
        body = _skill("cook").lower()
        for role in ("planner", "coder", "reviewer"):
            assert role in body
        assert "harvest" in body and "parent" in body
        assert "plate" in body and "parent" in body

    def test_uses_shared_resolver(self) -> None:
        body = _skill("cook")
        assert "../cheese/references/agent-resolution.md" in body
        assert "minimum power" in body.lower()


class TestUltracookHandoffContract:
    def test_uses_versioned_runtime_transaction(self) -> None:
        contract = _read(SKILLS_DIR / "cheese" / "references" / "work-contract.md")
        formatting = _read(SKILLS_DIR / "cheese" / "references" / "formatting.md")
        assert "handoff-commit" in contract
        assert "handoff-resolve" in contract
        assert ".cheese/<phase>/<work-id>/<operation-id>-<slug>.md" in contract
        assert "never flat" in formatting

    def test_resolver_actions_are_explicit(self) -> None:
        body = _skill("cook")
        for action in ("halt", "done", "dispatch", "hold", "tasks", "unavailable"):
            assert action in body


class TestPhaseHandoffContract:
    @pytest.mark.parametrize("skill_name", ["cook", "cure"])
    def test_phase_commits_and_resolves_versioned_handoff(self, skill_name: str) -> None:
        body = _skill(skill_name)
        assert "handoff-commit" in body
        assert "handoff-resolve" in body
        assert "WorkRecord" in body


class TestUltracookExistingHandoffsGuard:
    """The re-entry guard (refuse to wipe existing handoffs) now lives in
    /cook's Fan pathway, under its own `### Existing handoffs guard`."""

    def test_refuses_to_wipe_existing_handoffs(self) -> None:
        body = _skill("cook")
        # If handoffs already exist for the slug, cook stops and points
        # the user at /cheese --continue or a manual rm. No flag-driven wipe.
        assert "/cheese --continue" in body
        # Spell out the manual reset path — `rm` is an explicit instruction.
        assert "rm" in body.lower()
        # No surprise --restart flag (we explicitly dropped that idea).
        assert "--restart" not in body


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


def _mold_high_blast_handoff_menu() -> str:
    """The option list under mold's non-decomposable high-blast-radius handoff
    branch, sliced the same way as `_mold_low_medium_handoff_menu` so
    assertions target this branch's own text, not unrelated prose elsewhere
    in the skill that happens to mention "fresh" and "context" separately.
    """
    body = _skill("mold")
    start = body.index("**Non-decomposable, high-blast-radius specs")
    end = body.index("**Non-decomposable, low- or medium-blast-radius specs", start)
    return body[start:end]


class TestMoldHighBlastHandoff:
    def test_offers_ultracook(self) -> None:
        # /ultracook retired; its fresh-context-isolation pipeline is now
        # /cook --auto, offered directly in the high-blast-radius branch.
        menu = _mold_high_blast_handoff_menu()
        assert "/cook --auto" in menu, (
            "mold's handoff must offer /cook --auto for high-blast-radius specs"
        )
        assert "fresh-context isolation" in menu.lower(), (
            "mold's high-blast branch must offer fresh-context isolation"
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
    prose (which also references /cook --auto).
    """
    body = _skill("mold")
    start = body.index("**Non-decomposable, low- or medium-blast-radius specs")
    end = body.index("The internal `mode` signal", start)
    return body[start:end]


class TestMoldLowMediumHandoff:
    def test_offers_ultracook_option(self) -> None:
        # /ultracook retired; its merged replacement is /cook --auto,
        # offered alongside plain /cook in this branch's own option list.
        menu = _mold_low_medium_handoff_menu()
        assert "/cook <spec-path>" in menu, (
            "mold's low/medium handoff menu must offer plain /cook"
        )
        assert "/cook --auto <spec-path>" in menu, (
            "mold's low/medium handoff menu must offer /cook --auto as the "
            "auto-review option that replaced the standalone /ultracook choice"
        )

    # test_states_fast_path_cost removed: the fast-path-cost description was
    # specific to a standalone /ultracook menu option that no longer exists —
    # it merged into /cook --auto. The fast-path concept itself now lives in
    # /cook's own `### Mode selection` section (see TestUltracookModeGate),
    # not in mold's menu prose.

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

    def test_public_docs_name_cook_as_the_orchestrator(self) -> None:
        readme = _read(REPO_ROOT / "README.md")
        agents = _read(REPO_ROOT / "AGENTS.md")

        assert "`/cook` is the single implementation orchestrator" in readme
        assert "Compatibility redirect to `/cook`" in readme
        assert "milknado (MCP) | Mikado task-graph backend for `/cook`'s fan-path" in readme
        assert "Single implementation orchestrator" in agents
        assert "milknado (mikado task-graph backend for `/cook`'s fan pathway)" in agents


# ---------------------------------------------------------------------------
# Cross-skill integrity: phase reports use versioned runtime transactions.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("skill_name", ["age", "press", "cook", "cure"])
def test_phase_reports_use_versioned_destination_contract(skill_name: str) -> None:
    body = _skill(skill_name)
    assert "status: ok" in body, f"{skill_name} must document successful status"
    assert "next_phase" in body, f"{skill_name} must document its destination"
    assert "handoff-commit" in body, f"{skill_name} must commit through the runtime"


@pytest.mark.parametrize("skill_name", ["age", "press", "cook", "cure"])
def test_phase_handoff_documents_artifact_field(skill_name: str) -> None:
    """The spec's minimum handoff schema is four lines: status, next,
    artifact, orientation. The first parametrized test covers status+next;
    this one locks down `artifact:` so a future edit cannot silently shrink
    the schema and break the orchestrator's halt-and-surface contract.
    """
    body = _skill(skill_name)
    assert "artifact path" in body or "artifact returned" in body or "artifact returned by" in body
    assert "handoff-commit" in body


class TestUltracookReadsCommittedArtifact:
    def test_rule_present_in_skill_md(self) -> None:
        body = _skill("cook").lower()
        assert "artifact path" in body and "returned" in body
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
        body = _skill("cook")
        assert "### Existing work guard" in body
        assert "WorkRecord" in body
        assert "/cheese --continue" in body


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
        body = _skill("cook")
        body_lower = body.lower()
        # The override must be visible in the fan-pathway spawn contract.
        # Acceptable phrasings: "runs only its phase", "and stops", or the
        # equivalent no-chain isolation wording.
        assert "runs only its phase" in body_lower, (
            "cook's spawn prompt must explicitly direct the sub-agent "
            "not to chain forward to the next phase"
        )

    def test_dedicated_no_chain_section_present(self) -> None:
        body = _skill("cook")
        # The contract is critical enough to deserve its own section so
        # future contributors can find it from the table of contents.
        assert "no-chain" in body.lower() or "isolation directive" in body.lower(), (
            "cook must dedicate a section to the no-chain isolation "
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
        # /ultracook's literal 7-spawn table (3 full, un-scoped age
        # invocations) retired along with it. /cook's own single-coder auto
        # chain uses a different, valid design: one initial full age, then
        # up to two SCOPED re-verification ages (`/age --scope <path> --auto`)
        # capped at two cure passes — same terminal-in-age guarantee, a
        # different literal shape. Assert on cook's actual chain instead of
        # forcing the old table format to reappear.
        body = _skill("cook")
        assert "action: done" in body
        assert "/age <slug> --auto" in body, "cook's chain must include the initial full age"
        assert "/age --scope <touched-paths> --auto" in body, (
            "cook's chain must include the scoped re-verification age that "
            "runs after each cure pass"
        )
        assert "two cure passes" in body.lower()


class TestUltracookCapEnforcedByChainLength:
    """Mechanism-B contract: the two-cure-pass cap is enforced by the fan
    pathway's/auto-chain's fixed chain length, not by age tracking the pass
    count or writing a special cap-enforcing `next: done`. Fresh-context age
    cannot count prior cure passes — any contract requiring it to "see the
    cap reached" is non-functional. These tests lock the chosen mechanism in
    so a future edit cannot silently revert to the broken hybrid contract."""

    def test_ultracook_says_chain_length_enforces_cap(self) -> None:
        body = _skill("cook")
        body_lower = body.lower()
        # Mechanism-B signal: somewhere in cook's body, the cap must be
        # attributed to chain length / table length, not to age.
        assert "chain length" in body_lower or "table length" in body_lower or (
            "fixed chain" in body_lower
        ), "cook must declare that chain length (not age) enforces the cap"

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
        body = _skill("cook")
        assert "handoff-resolve" in body
        assert "read_handoff_slug" not in body

    def test_runtime_path_is_authoritative(self) -> None:
        body = _skill("cook")
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
        body = _skill("cook")
        assert "Mode selection" in body, (
            "cook must document a mode-selection gate"
        )
        assert "decomposer" in body.lower(), "the decomposer is the mode gate"

    def test_mode_selector_and_threshold_referenced(self) -> None:
        body = _skill("cook")
        assert "PARALLEL_THRESHOLD" in body, (
            "cook must name the canonical PARALLEL_THRESHOLD constant"
        )
        # The mode subcommand picks linear|parallel deterministically.
        assert "ultracook.pyz mode" in body or "pyz mode --count" in body, (
            "cook must invoke the deterministic mode selector"
        )

    def test_two_or_more_curds_is_parallel(self) -> None:
        body = _skill("cook")
        body_lower = body.lower()
        assert "2 or more" in body_lower or "2+" in body, (
            "cook must state 2+ curds routes to parallel mode"
        )
        assert "1-curd spec runs" in body and "linear mode" in body_lower, (
            "cook must state a 1-curd spec stays linear"
        )

    def test_fast_path_skips_decomposer_for_single_low_or_medium_blast_curd(self) -> None:
        body = _skill("cook")
        body_lower = body.lower()
        assert "fast-path" in body_lower, (
            "cook must document a deterministic fast-path before the decompose step"
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
    """Wave-fan mechanics use typed fresh-context phase agents in one curd
    worktree, then repeat review and final age over the merged diff."""

    def test_parallel_mode_section_present(self) -> None:
        # Retired /ultracook's `## Parallel mode` heading is now /cook's
        # `## Fan pathway` — same mechanics, new home, legitimate rename.
        body = _skill("cook")
        assert "## Fan pathway" in body

    def test_per_curd_pipeline_documented(self) -> None:
        body = _skill("cook")
        # Per-curd pipeline uses the parallel-curd phase table.
        assert "parallel-curd" in body, (
            "the fan pathway must run each curd on the parallel-curd phase table"
        )

    def test_post_merge_final_age_documented(self) -> None:
        body = _skill("cook")
        body_lower = body.lower()
        assert "parallel-postmerge" in body, (
            "the fan pathway must use the parallel-postmerge table"
        )
        assert "reviewer(final age)" in body_lower
        assert "post-merge" in body_lower or "merged diff" in body_lower


class TestUltracookWorktreeLifecycle:
    """The worktree helper harvests a curd branch with no fetch and tears the
    worktree + branch down afterward — no leaks (acceptance #5)."""

    def test_harvest_no_fetch(self) -> None:
        body = _skill("cook")
        body_lower = body.lower()
        assert "worktree harvest" in body_lower, "the fan pathway must harvest curd branches"
        assert "no `git fetch`" in body or "no git fetch" in body_lower or (
            "shared" in body_lower and "object store" in body_lower
        ), "harvest must state it needs no git fetch (shared object store)"

    def test_teardown_leaves_no_leak(self) -> None:
        body = _skill("cook")
        body_lower = body.lower()
        assert "worktree teardown" in body_lower, "the fan pathway must tear worktrees down"
        assert "leak" in body_lower, (
            "the teardown contract must state no worktree/branch leaks"
        )
        assert "worktree-agent-" in body or ".claude/worktrees/agent-" in body, (
            "teardown must name the worktree/branch pattern that must not leak"
        )


class TestUltracookMilknadoSeam:
    """milknado.probe() returns engine/tracker/none; the fan pathway runs with
    milknado absent (native fan-out), and the self-verify vs verify-until-green
    parity is stated (acceptance #4)."""

    def test_three_probe_roles_documented(self) -> None:
        body = _skill("cook")
        body_lower = body.lower()
        assert "engine" in body_lower and "tracker" in body_lower, (
            "the milknado seam must name the engine and tracker roles"
        )
        assert "ultracook.pyz milknado" in body, (
            "cook must invoke the deterministic milknado probe"
        )

    def test_native_path_runs_without_milknado(self) -> None:
        body = _skill("cook")
        body_lower = body.lower()
        assert "native fan-out" in body_lower, (
            "the fan pathway must document the native fan-out path when milknado is absent"
        )

    def test_parity_difference_stated(self) -> None:
        body = _skill("cook")
        body_lower = body.lower()
        # The intentional parity difference must be explicit.
        assert "self-verify" in body_lower, (
            "native curds must be documented as self-verifying (gates in-worker)"
        )
        assert "verify-until-green" in body_lower, (
            "milknado's verify-until-green must be named as the parity difference"
        )


class TestUltracookAgentResolution:
    """/cook resolves typed roles through the shared minimum-power protocol
    (retired /ultracook's own copy of this contract)."""

    def test_shared_resolution_protocol_documented(self) -> None:
        body = _skill("cook").lower()
        assert "agent-resolution.md" in body
        # The shared reference (`../cheese/references/agent-resolution.md`)
        # and cook itself both say "minimum power", not the old ultracook
        # spec's "minimum capable power" — a consistent codebase convention.
        assert "minimum power" in body
        assert "agent_resolution" in body

    def test_typed_phase_roles_documented(self) -> None:
        body = _skill("cook").lower()
        assert "planner/general" in body
        assert "coder(cook)" in body
        assert "reviewer(age)" in body
        assert "parent ownership for harvest and plate" in body

    def test_terminal_age_gate_documented(self) -> None:
        body = _skill("cook").lower()
        assert "publishable only when its committed artifact resolves to `action: done`" in body
        assert "dispatch back to cure, halt, or missing/malformed result is not publishable" in body


class TestUltracookRecoveryPaths:
    """The fan pathway surfaces a worker-exhaustion recovery path and an
    aggregate-gate failure path (issue #194, acceptance #7)."""

    def test_worker_exhaustion_recovery(self) -> None:
        body = _skill("cook")
        body_lower = body.lower()
        assert "#194" in body or "194" in body, (
            "cook must cite issue #194 for the recovery paths"
        )
        assert "exhaust" in body_lower and "retry" in body_lower, (
            "the fan pathway must document worker-exhaustion recovery (retry once)"
        )

    def test_aggregate_gate_failure_distinguishes_conflict_from_drift(self) -> None:
        body = _skill("cook")
        body_lower = body.lower()
        assert "aggregate" in body_lower, (
            "the fan pathway must document the aggregate-gate failure path"
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
        body = _skill("cook").lower()
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
        body = _skill("cook")
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
        body = _skill("cook")
        assert "## --resume <slug>" in body, "a dedicated --resume section must exist"
        assert "git cat-file -e" in body, (
            "resume must verify recorded commit SHAs still exist (rebase guard)"
        )
        assert "phase_summary" in body and "carry_forward" in body, (
            "resume must read phase_summary/carry_forward for cross-seam continuity"
        )

    def test_phase_strings_agree_across_writer_reader_and_schema(self) -> None:
        # The whole point of --resume: a phase string written by the topology
        # (wave-fan mechanics) prose must round-trip through the reader
        # section and the schema enum. Drift in any one of the three (edit
        # one place, forget the others) silently breaks resume.
        import json
        import re

        body = _skill("cook")
        schema_path = SKILLS_DIR / "ultracook" / "references" / "manifest-schema.json"
        schema_enum = json.loads(_read(schema_path))["properties"]["phase"]["enum"]

        # cook's heading is `### --resume <slug>` (one level deeper than
        # retired ultracook's top-level `## --resume <slug>`).
        resume_section = body.split("\n### --resume <slug>", 1)[1]
        # Accept either ASCII `->` (cook's convention) or the original
        # unicode `→` — the arrow glyph isn't the guarantee under test.
        arrow_span = re.search(
            r"`([a-z_]+(?: (?:->|→) [a-z_]+)+)`", resume_section
        )
        assert arrow_span, "resume section must list the ordered phase enum"
        reader_enum = [
            p.strip() for p in re.split(r" -> | → ", arrow_span.group(1))
        ]

        # Writer: every `--phase <X>` the wave-fan-mechanics prose (before
        # the reader section) tells the orchestrator to set.
        topology = body.split("\n### --resume <slug>", 1)[0]
        writer_phases = set(re.findall(r"--phase ([a-z_]+)", topology))

        assert reader_enum == schema_enum, (
            "reader arrow-list must match the schema phase enum exactly (order + members)"
        )
        assert writer_phases == set(schema_enum) - {"gate_approved"}, (
            "the wave-fan mechanics must write every schema phase past the "
            f"decomposer scaffold (gate_approved); writer={sorted(writer_phases)} "
            f"schema={schema_enum}"
        )
