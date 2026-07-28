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


def _skill_corpus(name: str) -> str:
    """SKILL.md body plus every skills/<name>/references/*.md file, concatenated.

    Sub-protocol prose that moved out of SKILL.md during the token-budget
    trim still lives in the routed reference files; tests asserting on that
    prose must search the corpus, not just the trimmed body.
    """
    body = _skill(name)
    refs_dir = SKILLS_DIR / name / "references"
    if refs_dir.is_dir():
        for ref_path in sorted(refs_dir.glob("*.md")):
            body += "\n" + _read(ref_path)
    return body


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
        body = _skill_corpus("cook")
        # Single-coder auto chain: press -> age -> cure -> scoped re-verify
        # age, capped at two cure passes, terminal next: done.
        auto_idx = body.find("## Auto mode")
        assert auto_idx != -1, "cook must document `## Auto mode`"
        auto_section = body[auto_idx:]
        cursor = 0
        for invocation in (
            "/press <slug> --auto",
            "/age <slug> --auto",
            "/cure <slug> --auto --stake medium+",
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
        body = _skill_corpus("cook")
        for invocation in (
            "/press <slug> --auto",
            "/age <slug> --auto",
            "/cure <slug> --auto --stake medium+",
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


class TestUltracookHandoffSchema:
    """The handoff-slug schema (status/next/artifact/orientation) now lives
    in /cook's own `## Handoff slug` section for the fan pathway."""

    def test_documents_five_line_slug_shape(self) -> None:
        body = _skill("cook")
        for field in HANDOFF_SCHEMA_FIELDS:
            assert field in body, f"handoff schema missing `{field}` field"
        # Both halt and ok terminal states must be reachable.
        assert "halt" in body.lower()
        assert "next:" in body and "done" in body

    def test_paths_are_under_dot_cheese_phase_slug(self) -> None:
        body = _skill_corpus("cook")
        # Each phase's handoff lives at a predictable path; the orchestrator
        # has to know where to read after spawning.
        for phase in ("cook", "press", "age", "cure"):
            assert f".cheese/{phase}/" in body, (
                f"missing .cheese/{phase}/<slug>.md handoff path"
            )


class TestUltracookExistingHandoffsGuard:
    """The re-entry guard (refuse to wipe existing handoffs) now lives in
    /cook's Fan pathway, under its own `### Existing handoffs guard`."""

    def test_refuses_to_wipe_existing_handoffs(self) -> None:
        body = _skill_corpus("cook")
        # If handoffs already exist for the slug, cook stops and points
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


def _mold_high_blast_handoff_menu() -> str:
    """The option list under mold's non-decomposable high-blast-radius handoff
    branch, sliced the same way as `_mold_low_medium_handoff_menu` so
    assertions target this branch's own text, not unrelated prose elsewhere
    in the skill that happens to mention "fresh" and "context" separately.
    """
    body = _skill_corpus("mold")
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
        body = _skill_corpus("mold")
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
    body = _skill_corpus("mold")
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
        body = _skill_corpus("cheese")
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
        body = _skill_corpus("cheese")
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
# session-convergence-wheypoint — provenance header fields + join/split verbs.
#
# The four optional provenance fields (session/git/created/parents) are
# additive and backward-compatible: a pre-provenance note stays valid, and the
# orientation line stays the FIRST non-key line so /cheese --continue's
# key-based parse is unaffected (spec acceptance #4/#5). These lock the
# placement + optionality invariant and the join/split lineage cardinality
# (acceptance #2/#3) against a silent reorder or a dropped contract clause.
# ---------------------------------------------------------------------------


def _handoff_schema_fence() -> list[str]:
    """Return the canonical ordered field list — the header-schema block under
    `## Handoff slug`, from its `status: ok | gated:` line through the
    orientation placeholder — as its individual lines. Sliced by anchor rather
    than by fence so it is insensitive to the surrounding code-fence syntax."""
    lines = _skill("wheypoint").splitlines()
    start = next(
        (i for i, ln in enumerate(lines) if ln.startswith("status: ok | gated:")),
        None,
    )
    if start is None:
        raise AssertionError("wheypoint must carry the `status: ok | gated:` header schema")
    end = next(
        (
            i
            for i, ln in enumerate(lines[start:], start)
            if ln.lstrip().startswith("<one-line orientation")
        ),
        None,
    )
    if end is None:
        raise AssertionError("wheypoint header schema must end with the orientation line")
    return lines[start : end + 1]


class TestWheypointProvenance:
    PROVENANCE_KEYS = ("session:", "git:", "created:", "parents:")

    def test_schema_lists_all_provenance_fields(self) -> None:
        fence = "\n".join(_handoff_schema_fence())
        for key in self.PROVENANCE_KEYS:
            assert key in fence, (
                f"wheypoint header schema must document the provenance field `{key}`"
            )

    def test_provenance_fields_sit_between_artifact_and_orientation(self) -> None:
        # The backward-compat linchpin: orientation stays the first non-key
        # line, so every provenance field must appear after `artifact:` and
        # before the orientation placeholder. A reorder pushing a provenance
        # key below orientation would break /cheese --continue's key-based
        # parse and silently consume a wrong orientation.
        lines = _skill("wheypoint").splitlines()
        orient_i = next(
            (
                i
                for i, ln in enumerate(lines)
                if ln.lstrip().startswith("<one-line orientation")
            ),
            None,
        )
        assert orient_i is not None, (
            "wheypoint schema must keep the `<one-line orientation` placeholder"
        )
        artifact_positions = [
            i for i, ln in enumerate(lines[:orient_i]) if ln.startswith("artifact:")
        ]
        assert artifact_positions, (
            "wheypoint schema must document `artifact:` above the orientation line"
        )
        artifact_i = max(artifact_positions)
        for key in self.PROVENANCE_KEYS:
            positions = [i for i, ln in enumerate(lines) if ln.startswith(key)]
            assert any(artifact_i < i < orient_i for i in positions), (
                f"provenance field `{key}` must sit between artifact: and the "
                f"orientation line (orientation stays the first non-key line)"
            )

    def test_provenance_documented_optional_and_backward_compatible(self) -> None:
        body = _skill("wheypoint").lower()
        # Scope the optionality check to the `### Provenance fields` block so
        # it cannot be satisfied by an unrelated "optional" elsewhere in the
        # file (the word appears many times outside the provenance section).
        start = body.find("### provenance fields")
        assert start != -1, "wheypoint must carry a `### Provenance fields` section"
        end = body.find("\n### ", start + 1)
        section = body[start:end] if end != -1 else body[start:]
        assert "optional" in section, (
            "provenance fields must be documented as optional in the "
            "`### Provenance fields` section"
        )
        assert "pre-provenance" in body, (
            "wheypoint must state pre-provenance notes (none of the new keys) stay valid"
        )


class TestWheypointJoinSplitVerbs:
    def test_join_documented_with_both_parent_slugs(self) -> None:
        body = _skill("wheypoint")
        assert "--join" in body, "wheypoint must document the --join verb"
        assert "parents: [<slugA>, <slugB>]" in body or "parents: [A, B]" in body, (
            "--join must write one note whose parents lists both source slugs"
        )

    def test_split_documented_with_current_slug_as_parent(self) -> None:
        body = _skill("wheypoint")
        assert "--split" in body, "wheypoint must document the --split verb"
        assert (
            "parents: [<current-slug>]" in body or "parents: [<current>]" in body
        ), "--split children must each be parented on the current slug"


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


@pytest.mark.parametrize("skill_name", ["age", "press", "cook", "cure"])
def test_phase_handoff_documents_artifact_field(skill_name: str) -> None:
    """The spec's minimum handoff schema is four lines: status, next,
    artifact, orientation. The first parametrized test covers status+next;
    this one locks down `artifact:` so a future edit cannot silently shrink
    the schema and break the orchestrator's halt-and-surface contract.
    """
    body = _skill_corpus(skill_name)
    assert "artifact:" in body, (
        f"{skill_name} handoff schema must document the `artifact:` field"
    )


class TestUltracookReadsSlugFile:
    """The orchestrator MUST read the slug file after each sub-agent
    returns — inferring success from the sub-agent's last line of output
    silently bypasses the halt-and-surface contract.
    """

    def test_rule_present_in_skill_md(self) -> None:
        body = _skill_corpus("cook")
        # Acceptable phrasings: "read the file", "read each phase's
        # handoff slug", or any explicit instruction not to infer from
        # stdout. Match on the substantive prohibition.
        body_lower = body.lower()
        assert "read the file" in body_lower or "read the slug" in body_lower or (
            "read each phase" in body_lower and "handoff" in body_lower
        ), "cook must instruct the fan pathway to read the slug file"
        assert "stdout" in body_lower or "last line" in body_lower, (
            "cook must explicitly forbid inferring success from sub-agent stdout"
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
        body = _skill_corpus("cook")
        # Slice to the existing-handoffs guard section only (cut at the next
        # top-level `## ` heading) so an unrelated third mention elsewhere in
        # the skill (e.g. the Handoff-slug schema) can't pad the count and
        # mask a shrink within the guard itself.
        start = body.index("## Existing handoffs guard")
        end = body.index("\n## Mode selection", start)
        guard_section = body[start:end]
        # The existing-handoffs guard must mention every phase's handoff
        # path at least twice (prose + the printed listing) — dropping it
        # from one site would still break the boundary contract.
        path = f".cheese/{phase}/"
        assert guard_section.count(path) >= 2, (
            f"cook must reference {path}<slug>.md at least twice in its "
            f"existing-handoffs guard (count<2 means one site silently shrank)"
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
        body = _skill_corpus("cheese")
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
        body = _skill_corpus("cook")
        body_lower = body.lower()
        # The override must be visible in the Agent() prompt template.
        # Acceptable phrasings: "do not chain forward", "this phase only",
        # "stop" + "do not invoke the next phase", or the equivalent.
        assert "do not chain forward" in body_lower or "this phase only" in body_lower, (
            "cook's spawn prompt must explicitly direct the sub-agent "
            "not to chain forward to the next phase"
        )

    def test_dedicated_no_chain_section_present(self) -> None:
        body = _skill("cook")
        # The contract is load-bearing enough to deserve its own section
        # so future contributors can find it from the table of contents.
        assert "no-chain" in body.lower() or "isolation directive" in body.lower(), (
            "cook must dedicate a section to the no-chain isolation "
            "directive — without it the per-phase isolation guarantee is "
            "easy to remove silently"
        )


@pytest.mark.parametrize("phase", ["cook", "press", "age", "cure"])
def test_phase_documents_ultracook_no_chain_override(phase: str) -> None:
    """Every phase ultracook spawns must explicitly document that, when
    invoked from ultracook with the no-chain directive, it writes its
    handoff slug and stops instead of chaining forward."""
    body = _skill_corpus(phase)
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
        # /ultracook's literal 7-spawn table (3 full, un-scoped age
        # invocations) retired along with it. /cook's own single-coder auto
        # chain uses a different, valid design: one initial full age, then
        # up to two SCOPED re-verification ages (`/age --scope <path> --auto`)
        # capped at two cure passes — same terminal-in-age guarantee, a
        # different literal shape. Assert on cook's actual chain instead of
        # forcing the old table format to reappear.
        body = _skill_corpus("cook")
        assert "next: done" in body
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
        body = _skill_corpus("cook")
        body_lower = body.lower()
        # Mechanism-B signal: somewhere in cook's body, the cap must be
        # attributed to chain length / table length, not to age.
        assert "chain length" in body_lower or "table length" in body_lower or (
            "fixed chain" in body_lower
        ), "cook must declare that chain length (not age) enforces the cap"

    def test_ultracook_says_age_next_is_informational(self) -> None:
        body = _skill_corpus("cook")
        body_lower = body.lower()
        # Under mechanism B, age's `next:` is descriptive: it reports what
        # age observed, but doesn't drive cap enforcement. The contract
        # must spell that out so a future edit doesn't restore the
        # contradictory "age writes the cap-enforcing next: done" claim.
        assert "informational" in body_lower or "informative" in body_lower, (
            "cook must spell out that age's next: field is informational, "
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
        body = _skill_corpus("mold")
        body_lower = body.lower()
        # The high-blast-radius branch heading or surrounding prose must
        # carry the "high only" qualifier so the scope is unambiguous.
        assert "high only" in body_lower or "verdict `high` only" in body, (
            "mold's high-blast branch must restrict to verdict `high` only, "
            "not `medium or high`"
        )

    def test_medium_keeps_standard_handoff(self) -> None:
        body = _skill_corpus("mold")
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
        body = _skill_corpus("cheese")
        body_lower = body.lower()
        assert "gated:" in body, (
            "cheese --continue must document a gated: routing branch"
        )
        # The three directions the reader must offer.
        assert "research" in body_lower and "decide" in body_lower and "build" in body_lower, (
            "gated: branch must ask the user which direction: research / decide / build"
        )

    def test_gated_does_not_auto_dispatch(self) -> None:
        body = _skill_corpus("cheese")
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
        body = _skill_corpus("cheese")
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
        body = _skill_corpus("cheese")
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
        body = _skill_corpus("cheese")
        body_lower = body.lower()
        # order: missing -> stop and ask for a corrected handoff.
        assert "order:" in body and "required" in body_lower, (
            "list branch must treat order: as required"
        )

    def test_parallel_and_sequential_dispatch(self) -> None:
        body = _skill_corpus("cheese")
        body_lower = body.lower()
        assert "order: parallel" in body and "order: sequential" in body, (
            "list branch must handle both order: parallel and order: sequential"
        )
        # Parallel fans out concurrent read agents in the same turn.
        assert "concurrent" in body_lower or "same turn" in body_lower, (
            "order: parallel must dispatch concurrent read agents in the same turn"
        )

    def test_rejects_write_skills_in_inline_list(self) -> None:
        body = _skill_corpus("cheese")
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
        body = _skill_corpus("cheese")
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
        body = _skill_corpus("cheese")
        # The heavyweight write-isolation path must be untouched.
        assert "mode: parallel" in body and "tasks:" in body, (
            "the heavyweight mode: parallel + tasks: path must remain documented"
        )
        assert "worktree_strategy" in body, (
            "parallel write-isolation strategy must remain documented"
        )


class TestUltracookDeterministicPhaseLoop:
    """The phase loop must invoke the deterministic helpers — read_handoff_slug
    for slug parsing and phase_decision for the next-action verdict — so the
    orchestrator never judges phase transitions by eye."""

    def test_read_handoff_slug_referenced(self) -> None:
        body = _skill_corpus("cook")
        assert "read_handoff_slug" in body, (
            "cook must reference read_handoff_slug in the phase loop so "
            "slug parsing is deterministic, not eyeballed"
        )

    def test_phase_decision_referenced(self) -> None:
        body = _skill_corpus("cook")
        assert "phase_decision" in body, (
            "cook must reference phase_decision in the phase loop so "
            "the next-action verdict is deterministic"
        )


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
        body = _skill_corpus("cook")
        assert "Mode selection" in body, (
            "cook must document a mode-selection gate"
        )
        assert "decomposer" in body.lower(), "the decomposer is the mode gate"

    def test_mode_selector_and_threshold_referenced(self) -> None:
        body = _skill_corpus("cook")
        assert "PARALLEL_THRESHOLD" in body, (
            "cook must name the canonical PARALLEL_THRESHOLD constant"
        )
        # The mode subcommand picks linear|parallel deterministically.
        assert "ultracook.pyz mode" in body or "pyz mode --count" in body, (
            "cook must invoke the deterministic mode selector"
        )

    def test_two_or_more_curds_is_parallel(self) -> None:
        body = _skill_corpus("cook")
        body_lower = body.lower()
        assert "2 or more" in body_lower or "2+" in body, (
            "cook must state 2+ curds routes to parallel mode"
        )
        assert "1-curd spec runs" in body and "linear mode" in body_lower, (
            "cook must state a 1-curd spec stays linear"
        )

    def test_fast_path_skips_decomposer_for_single_low_or_medium_blast_curd(self) -> None:
        body = _skill_corpus("cook")
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
        body = _skill_corpus("cook")
        # Per-curd pipeline uses the parallel-curd phase table.
        assert "parallel-curd" in body, (
            "the fan pathway must run each curd on the parallel-curd phase table"
        )

    def test_post_merge_final_age_documented(self) -> None:
        body = _skill_corpus("cook")
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
        body = _skill_corpus("cook")
        body_lower = body.lower()
        assert "worktree harvest" in body_lower, "the fan pathway must harvest curd branches"
        assert "no `git fetch`" in body or "no git fetch" in body_lower or (
            "shared" in body_lower and "object store" in body_lower
        ), "harvest must state it needs no git fetch (shared object store)"

    def test_teardown_leaves_no_leak(self) -> None:
        body = _skill_corpus("cook")
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
        body = _skill_corpus("cook")
        body_lower = body.lower()
        assert "engine" in body_lower and "tracker" in body_lower, (
            "the milknado seam must name the engine and tracker roles"
        )
        assert "ultracook.pyz milknado" in body, (
            "cook must invoke the deterministic milknado probe"
        )

    def test_native_path_runs_without_milknado(self) -> None:
        body = _skill_corpus("cook")
        body_lower = body.lower()
        assert "native fan-out" in body_lower, (
            "the fan pathway must document the native fan-out path when milknado is absent"
        )

    def test_parity_difference_stated(self) -> None:
        body = _skill_corpus("cook")
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
        body = _skill_corpus("cook").lower()
        assert "planner/general" in body
        assert "coder(cook)" in body
        assert "reviewer(age)" in body
        assert "parent ownership for harvest and plate" in body

    def test_terminal_age_gate_documented(self) -> None:
        body = _skill("cook").lower()
        assert "publishable only with `next: done`" in body
        assert "`next: cure` or a missing `next` halts" in body


class TestUltracookRecoveryPaths:
    """The fan pathway surfaces a worker-exhaustion recovery path and an
    aggregate-gate failure path (issue #194, acceptance #7)."""

    def test_worker_exhaustion_recovery(self) -> None:
        body = _skill_corpus("cook")
        body_lower = body.lower()
        assert "#194" in body or "194" in body, (
            "cook must cite issue #194 for the recovery paths"
        )
        assert "exhaust" in body_lower and "retry" in body_lower, (
            "the fan pathway must document worker-exhaustion recovery (retry once)"
        )

    def test_aggregate_gate_failure_distinguishes_conflict_from_drift(self) -> None:
        body = _skill_corpus("cook")
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
        body = _skill_corpus("cook").lower()
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
        body = _skill_corpus("cook")
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
        body = _skill_corpus("cook")
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

        body = _skill_corpus("cook")
        schema_path = SKILLS_DIR / "ultracook" / "references" / "manifest-schema.json"
        schema_enum = json.loads(_read(schema_path))["properties"]["phase"]["enum"]

        # cook's heading is `### --resume <slug>` inline in SKILL.md, or
        # `## --resume <slug>` in the routed fan-pathway.md reference file
        # (one level shallower once it's a standalone file's own heading).
        for heading in ("\n### --resume <slug>", "\n## --resume <slug>"):
            parts = body.split(heading, 1)
            if len(parts) == 2:
                resume_section = parts[1]
                break
        else:
            raise AssertionError("cook corpus must carry a `--resume <slug>` heading")
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
