"""Regression tests for the `cheese` router findings of the round-2 cure.

Each test pins one prose contract that a review note found broken. The router is
prose, so the seam these tests protect is the prose itself: a later edit that
reintroduces the defect fails here instead of at dispatch time.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SKILL_DIR = REPO_ROOT / "skills" / "cheese"
CHEESE = SKILL_DIR / "SKILL.md"
REFERENCES = SKILL_DIR / "references"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


class TestMoldSkipsTheCookFastPath:
    """`review-cheese.md` blocker: a `mold` intent must not run Cook's check."""

    def test_skill_scopes_the_clarity_check_to_cook(self) -> None:
        body = _text(CHEESE)
        assert "Run Cook's fast-path check for a `cook` intent." in body
        assert "fast-path check for `cook` and `mold`" not in body

    def test_skill_routes_mold_to_its_user_mode(self) -> None:
        assert "Dispatch a `mold` intent to `/mold`'s user mode" in _text(CHEESE)

    def test_classification_and_escalation_agree_with_the_skill(self) -> None:
        for name in ("classification.md", "escalation.md"):
            body = _text(REFERENCES / name)
            assert "For `cook` and `mold`" not in body, name
            assert "`mold` intent skips" in body, name


class TestCurdBlockIsMigrationOnly:
    """`review-cheese.md` blocker: the curd block is not production state."""

    def test_decomposer_declares_the_migration_scope(self) -> None:
        body = _text(REFERENCES / "decomposer.md")
        assert "**Scope: explicit migration only.**" in body
        assert "The curd block is not production state." in body
        assert "Never persist a curd block as the selected production artifact." in body

    def test_decomposer_points_at_the_typed_planner_chain(self) -> None:
        body = _text(REFERENCES / "decomposer.md")
        for contract in ("PlannerRequest", "PlannerResult", "CurdPlan", "CurdResult"):
            assert f"`{contract}`" in body, contract
        assert "schema-intertwine.md" in body

    def test_every_producer_needs_an_explicit_migration_request(self) -> None:
        body = _text(REFERENCES / "decomposer.md")
        assert "Each producer acts only on an explicit migration request." in body


class TestCookOwnsOneFastPathContract:
    """`review-cheese.md` high: three files defined three eligibility rules."""

    OWNER_LINK: str = "[`../../cook/SKILL.md`](../../cook/SKILL.md) section Standalone fast-path"

    def test_classification_links_the_owner_instead_of_restating_it(self) -> None:
        body = _text(REFERENCES / "classification.md")
        assert self.OWNER_LINK in body
        assert "Do not restate the check here." in body
        assert "All three of:" not in body

    def test_routing_receipt_links_the_owner_instead_of_restating_it(self) -> None:
        body = _text(REFERENCES / "routing-receipt.md")
        assert self.OWNER_LINK in body
        assert "Do not restate the check here." in body
        assert "It must name a file or behavior." not in body


class TestGateExampleMatchesTheStandardMenu:
    """`edge-cook-cheese.md` medium: the Cook gate example had three options
    and omitted the standard Plate and checkpoint steps."""

    def test_example_carries_all_four_standard_options(self) -> None:
        body = _text(REFERENCES / "handoff-gate.md")
        example = body[body.index("handoff_gate:") : body.index("Every gate must include")]
        for option in ("harden-tests", "plate-it", "checkpoint-and-stop", "stop"):
            assert f"- id: {option}" in example, option

    def test_plate_option_forwards_the_publication_flag(self) -> None:
        body = _text(REFERENCES / "handoff-gate.md")
        assert "dispatch: /press <slug> --auto --open-pr" in body

    def test_stop_stays_the_last_option(self) -> None:
        body = _text(REFERENCES / "handoff-gate.md")
        example = body[body.index("handoff_gate:") : body.index("Every gate must include")]
        assert example.rindex("- id: stop") > example.rindex("- id: checkpoint-and-stop")


class TestOptionalPluginDetectionIsCapabilityBased:
    """`review-cheese.md` medium: exact Claude tool names miss other hosts."""

    def test_contract_matches_a_capability_not_one_name(self) -> None:
        body = _text(REFERENCES / "optional-plugins.md")
        assert "Match the capability, not one exact tool name." in body
        assert "A host renames and prefixes MCP tools." in body

    def test_probe_pattern_treats_every_prefix_as_a_match(self) -> None:
        body = _text(REFERENCES / "optional-plugins.md")
        assert "Each host prefixes these names differently." in body
        assert "Treat any prefix as a match." in body
        assert "Call the tool by the exact name that the host exposes." in body

    def test_skill_does_not_hard_code_one_grounding_tool_name(self) -> None:
        body = _text(CHEESE)
        assert "mcp__hallouminate__ground" not in body
        assert "Resolve both tool names through" in body


class TestArtifactHasOneMeaning:
    """`review-cheese.md` medium and `edge-cheese-mold.md` high: `artifact:`
    carried a prior report, a specification pointer, and a pull request."""

    def test_handback_contract_gives_each_reference_kind_a_carrier(self) -> None:
        body = _text(REFERENCES / "handback-contract.md")
        assert "`artifact:` has exactly one meaning." in body
        assert "| prior consumed report | `artifact:` |" in body
        assert "`handoff.spec_ref`" in body
        assert "| pull request reference | the `<pr-ref>` argument of `/affinage` |" in body

    def test_reference_kind_comes_from_the_carrier(self) -> None:
        body = _text(REFERENCES / "handback-contract.md")
        assert "Read the reference kind from its carrier, not from `next:`." in body

    def test_skill_carries_the_specification_pointer_in_spec_ref(self) -> None:
        body = _text(CHEESE)
        assert "It carries its durable specification pointer in the typed `spec_ref` field." in body
        assert "which always names the prior consumed report" in body

    def test_resume_reads_spec_ref_before_artifact(self) -> None:
        body = _text(REFERENCES / "continue-resume.md")
        assert "Read that pointer from the typed `spec_ref` field." in body
        assert "Read it from `artifact:` only for a legacy note that has no `spec_ref` value." in body


class TestAffinageResumeNormalizesItsReference:
    """`edge-cheese-affinage.md` high: `PR#<n>` failed Affinage's integer input."""

    def test_resume_normalizes_the_reference_before_dispatch(self) -> None:
        body = _text(REFERENCES / "continue-resume.md")
        assert "Normalize the value to a bare number before you emit the command." in body
        assert "`/affinage` and its `pr-status` command accept a number or a URL only." in body

    def test_resume_requires_a_stake_with_auto(self) -> None:
        body = _text(REFERENCES / "continue-resume.md")
        assert "Add `--auto` only together with an explicit `--stake <floor>` value." in body
        assert "Stop and ask for the floor when the user requested `--auto` without one." in body

    def test_artifact_overloading_is_confined_to_legacy_notes(self) -> None:
        body = _text(REFERENCES / "continue-resume.md")
        assert "This legacy note is the only carrier that overloads `artifact:`." in body


class TestLintChecksOneProjection:
    """`edge-cheese-wheypoint.md` medium: Cheese overstated the lint command."""

    def test_resume_sends_lineage_questions_to_resolve(self) -> None:
        body = _text(REFERENCES / "continue-resume.md")
        assert "`resolve` is the only command that checks the complete lineage." in body

    def test_resume_scopes_lint_to_the_projection(self) -> None:
        body = _text(REFERENCES / "continue-resume.md")
        assert "That command derives the document digest and the status again." in body
        assert "It does not check the lineage." in body


class TestResumeRoutesByDisposition:
    """`edge-cure-cheese.md` blocker: resume handled only an exact `ok`."""

    def test_resume_branches_on_the_disposition(self) -> None:
        body = _text(REFERENCES / "continue-resume.md")
        assert "**Branch on the disposition, not the status name.**" in body
        assert "handback-contract.md" in body

    def test_ok_with_concerns_proceeds_and_carries_the_concern(self) -> None:
        body = _text(REFERENCES / "continue-resume.md")
        assert "Treat `ok-with-concerns` exactly like `ok` for dispatch." in body
        assert "carry that concern into the dispatched phase" in body

    def test_needs_context_retries_the_same_phase_once(self) -> None:
        body = _text(REFERENCES / "continue-resume.md")
        assert "Re-dispatch the same phase with the named gap, and do not advance to `next:`." in body
        assert "Stop after one retry at that phase, and report `retry cap (1) reached`." in body

    def test_an_unknown_status_is_never_a_silent_proceed(self) -> None:
        body = _text(REFERENCES / "continue-resume.md")
        assert "An unrecognized status is an error." in body
        assert "Never treat it as `proceed`." in body


class TestPlateSummaryMatchesPlate:
    """`edge-cheese-plate.md` and `edge-plate-cheese.md`: the router named the
    wrong `--open-pr` consumer and only one of Plate's two question triggers."""

    def test_cure_is_the_documented_open_pr_consumer(self) -> None:
        body = _text(CHEESE)
        assert "`/cure` consumes this flag and sends the publication intent to terminal `/plate`." in body
        assert "`/plate` accepts no `--open-pr` flag of its own." in body

    def test_skill_names_both_plate_question_triggers(self) -> None:
        body = _text(CHEESE)
        assert "`/plate` asks before mutation when it recommends a stack." in body
        assert "`/plate` also asks before mutation when the shape is ambiguous." in body

    def test_coherence_check_keeps_the_same_two_triggers(self) -> None:
        body = _text(REFERENCES / "coherence-check.md")
        assert "It asks before mutation when a stack is recommended or shape is ambiguous." in body


class TestAgeAcceptsEveryReviewSource:
    """`edge-cheese-age.md` high: a valid pull request route stopped at the check."""

    def test_coherence_check_accepts_the_full_source_set(self) -> None:
        body = _text(REFERENCES / "coherence-check.md")
        line = next(line for line in body.splitlines() if "`/age` needs a review source" in line)
        for source in ("pull request", "branch", "commit reference", "range", "path scope"):
            assert source in line, source

    def test_coherence_check_delegates_source_validation_to_age(self) -> None:
        body = _text(REFERENCES / "coherence-check.md")
        assert "Let `/age` validate that source." in body
        assert "no branch divergence and no path scope" not in body

    def test_clarify_only_when_no_source_exists(self) -> None:
        body = _text(REFERENCES / "coherence-check.md")
        assert "Ask `clarify` first only when the input names no source at all." in body


class TestPublicationAndHardFlagPropagation:
    """`edge-cheese-cook.md` blockers: the redirect dropped `--hard`, and
    `--open-pr` could reach Cook without the user's authorization."""

    def test_ultracook_redirect_forwards_the_hard_flag(self) -> None:
        body = _text(CHEESE)
        row = next(line for line in body.splitlines() if "ultracook (retired)" in line)
        for flag in ("--open-pr", "--resume", "--auto", "--hard"):
            assert flag in row, flag

    def test_open_pr_needs_the_user(self) -> None:
        body = _text(CHEESE)
        assert "Forward `--open-pr` only when the user supplied it." in body
        assert "Never add `--open-pr` to a dispatch that the user did not authorize." in body

    def test_hard_forwards_on_every_accepting_route(self) -> None:
        body = _text(CHEESE)
        expected = "Forward `--hard` on every route that accepts it, including the retired `/ultracook` redirect."
        assert expected in body


class TestInternalBriesearchPacket:
    """`edge-cheese-briesearch.md` high: tier 2 lacked the slug and the mode."""

    def test_tier_two_allocates_the_parent_slug_before_the_call(self) -> None:
        body = _text(REFERENCES / "escalation.md")
        assert "Before a `/briesearch` call, allocate the parent mini-specification slug." in body
        assert "pass it with the question" in body

    def test_tier_two_marks_the_call_as_a_sidechain(self) -> None:
        body = _text(REFERENCES / "escalation.md")
        assert "Set `invocation: sidechain` on every internal `/briesearch` call." in body

    def test_tier_three_owns_every_user_question(self) -> None:
        body = _text(REFERENCES / "escalation.md")
        assert "An internal call never asks the user a question." in body
        assert "It returns `needs_input` with the open question instead." in body
        assert "Tier 3 owns every user question on this path." in body


class TestMoldOwnsItsSpecificationPath:
    """`edge-cheese-mold.md` high: Cheese named a path Mold's resolver forbids."""

    def test_escalation_never_names_a_literal_specification_path(self) -> None:
        body = _text(REFERENCES / "escalation.md")
        assert "Never name a literal specification path for `/mold`." in body
        assert "write `.cheese/specs/<slug>.md`" not in body

    def test_escalation_names_the_resolver_command(self) -> None:
        body = _text(REFERENCES / "escalation.md")
        assert "`artifact-path specs <slug>`" in body

    def test_escalation_still_forwards_the_returned_path(self) -> None:
        body = _text(REFERENCES / "escalation.md")
        assert "Use the explicit path that `/mold` returns." in body
        assert "Do not reduce it to a bare slug." in body


class TestHandbackClaimMatchesThePhaseRegistry:
    """`review-cheese.md` high: the writer claim covered unregistered phases."""

    REGISTERED: tuple[str, ...] = ("mold", "cook", "press", "age", "cure")

    def test_phase_handback_row_lists_only_registered_phases(self) -> None:
        body = _text(REFERENCES / "handback-contract.md")
        row = next(line for line in body.splitlines() if line.startswith("| Phase handback |"))
        for phase in self.REGISTERED:
            assert f"`/{phase}`" in row, phase
        assert "/affinage" not in row
        assert "/pasteurize" not in row

    def test_unregistered_phases_have_their_own_row(self) -> None:
        body = _text(REFERENCES / "handback-contract.md")
        row = next(
            line for line in body.splitlines() if line.startswith("| Unregistered report |")
        )
        assert "`/affinage`" in row and "`/pasteurize`" in row
        assert "written by hand" in row

    def test_contract_names_the_registry_as_the_gate(self) -> None:
        body = _text(REFERENCES / "handback-contract.md")
        assert "`schema-intertwine.md` lists the registered source phases." in body
        assert "They write the same preamble by hand and do not call the writer." in body

    def test_registry_projection_still_omits_the_unregistered_phases(self) -> None:
        """The narrowed claim is only correct while the registry omits them."""
        body = _text(REFERENCES / "schema-intertwine.md")
        assert "| affinage |" not in body
        assert "| pasteurize |" not in body


class TestPlannerAndIntegratorAreSeparateJobs:
    """`review-cheese.md` high: one role both required and forbade delegation."""

    def test_agent_resolution_marks_only_the_integrator_parent_owned(self) -> None:
        body = _text(REFERENCES / "agent-resolution.md")
        assert "The **integrator** owns the approval loop and stays with the parent agent." in body
        assert "Never delegate the integrator." in body
        assert "The **planner** is a delegated worker." in body

    def test_agent_resolution_names_the_planner_dispatch(self) -> None:
        body = _text(REFERENCES / "agent-resolution.md")
        assert "fresh-context planner on a `PlannerRequest`" in body
        assert "Record its `agent_resolution` block like any other delegated role." in body

    def test_routing_policy_row_agrees(self) -> None:
        body = _text(REFERENCES / "routing-policy.md")
        assert (
            "the integrator is parent-owned; the planner is a delegated fresh-context worker"
            in body
        )


class TestLiveDirectivesNeverWaiveIntegrityGates:
    """`review-cheese.md` high: the directive rule outranked the resume gates."""

    def test_skill_states_the_integrity_exception(self) -> None:
        body = _text(CHEESE)
        assert (
            "**Exception: a live directive never waives a resume integrity gate.**"
            in body
        )
        assert "still stop dispatch" in body

    def test_skill_defers_gate_detail_to_the_resume_reference(self) -> None:
        body = _text(CHEESE)
        assert "A live directive answers only the informed trust gate" in body
        assert "owns these gates." in body

    def test_resume_reference_keeps_the_same_rule(self) -> None:
        body = _text(REFERENCES / "continue-resume.md")
        assert "A live directive cannot waive that runtime gate." in body


class TestAffinageIsARoutableIntent:
    """`review-cheese.md` high: review-feedback work had no Affinage route."""

    def test_shape_index_lists_the_affinage_intent(self) -> None:
        body = _text(REFERENCES / "classification.md")
        assert "| affinage | — | `/affinage` |" in body

    def test_affinage_shape_precedes_the_generic_pull_request_rules(self) -> None:
        body = _text(REFERENCES / "classification.md")
        affinage = body.index("### affinage (`/affinage`)")
        age = body.index("### age (`/age`)")
        assert affinage < age
        assert "Match this shape before the generic pull request rules below." in body

    def test_skill_gives_affinage_a_default_target_and_a_stake_rule(self) -> None:
        body = _text(CHEESE)
        assert "- **affinage** — `/affinage <pr>` (recommended)." in body
        assert "Send `--auto` only with an explicit `--stake <floor>` value." in body

    def test_disambiguation_routes_review_feedback_verbs_to_affinage(self) -> None:
        body = _text(REFERENCES / "classification.md")
        assert 'on a pull request → `affinage`' in body
        assert "| `respond to the review comments on PR#142` | affinage |" in body


class TestFastPathProbeAccounting:
    """`review-cheese.md` high: `probes=0` must not hide a required probe."""

    def test_skill_skips_wiki_grounding_on_the_fast_path(self) -> None:
        body = _text(CHEESE)
        assert "Skip this step on the fast path." in body
        assert "the route is escalated" in body

    def test_coherence_check_skips_the_bounded_read_on_the_fast_path(self) -> None:
        body = _text(REFERENCES / "coherence-check.md")
        assert "Run this check on an escalated route only." in body
        assert "the router reads nothing" in body

    def test_receipt_marks_a_probing_route_as_escalated(self) -> None:
        body = _text(REFERENCES / "routing-receipt.md")
        assert "A route that runs either probe is not a fast route." in body
        assert "Count each probe and print `path=escalated` instead." in body
        assert (
            "Never print `probes=0` for a route that read a file or grounded the wiki."
            in body
        )
