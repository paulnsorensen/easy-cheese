import json
import re
from pathlib import Path
from typing import cast

ROOT = Path(__file__).resolve().parents[2]


def read(path: str) -> str:
    return (ROOT / path).read_text()


def test_plate_owns_commit_stack_and_review_shape_policy() -> None:
    skill = read("skills/plate/SKILL.md")
    topology = read("skills/plate/references/topology.md")
    stacks = read("skills/plate/references/stacks.md")
    credits = read("README.md").split("## Credits", maxsplit=1)[1]
    attribution_url = "https://jeff.sarn.at/blog/structuring-changes-with-the-code-reviewer-in-mind"
    flat_topology = " ".join(topology.split())
    assert "name: plate" in skill
    assert "\nmodel:" not in skill
    assert "commit-only" in skill.lower()
    assert "cohesive review unit" in topology
    assert "proceed without asking" in topology
    assert "independently reviewable ordered" in topology
    assert "never decides the shape on its own" in topology
    assert "exceeds roughly 400 changed code lines" in topology
    assert "**semantics-altering**" in topology
    assert "**semantics-preserving**" in topology
    assert attribution_url in credits
    assert attribution_url not in skill
    assert attribution_url not in topology
    assert "worktree-agent-repair-" in topology
    assert "A diff containing both is never one review unit" in flat_topology
    assert "changes an externally observable" in flat_topology
    assert "inherit its layer" in " ".join(stacks.split())
    assert "## Attribution" not in skill
    assert "Structuring Changes With The Code Reviewer in Mind" in credits
    assert "project-specific extensions" in " ".join(credits.split())
    assert "explicit user choice" in topology
    assert "It is authoritative" in topology
    assert "genuinely ambiguous" in topology
    assert "unchanged under `--auto`" in topology
    assert "before any commit" in topology
    assert "../cheese/references/ask-user-question.md" in topology
    assert "Existing PR" in skill
    assert "do not ask" in topology
    # The review-shape policy is one hop away, never duplicated in the core body.
    assert "semantics-altering" not in skill
    assert "plate-layout" not in skill


def test_plate_topology_question_record_is_valid_and_normalized() -> None:
    """Parse the emitted question record instead of matching phrases."""
    import yaml

    topology = read("skills/plate/references/topology.md")
    block = topology.split("```yaml\n", maxsplit=1)[1].split("\n```", maxsplit=1)[0]
    question = cast(dict[str, object], yaml.safe_load(block)["question"])
    assert set(question) == {"id", "prompt", "recommended", "multi", "options"}
    assert question["id"] == "plate-layout"
    assert question["multi"] is False
    assert question["recommended"] == "<single | stacked>"
    options = cast(list[dict[str, object]], question["options"])
    assert [option["id"] for option in options] == ["single", "stacked"]
    for option in options:
        assert set(option) == {"id", "label", "description"}
        assert cast(str, option["label"]).strip()
        assert cast(str, option["description"]).strip()

    normalization = topology.split("## Answer normalization", maxsplit=1)[1].split(
        "\n## ", maxsplit=1
    )[0]
    flat = " ".join(normalization.split())
    assert "returns free text with an `other:` prefix" in flat
    assert "only when its text is unambiguous" in flat
    assert "Ask one clarification question for every other answer" in flat
    assert "Halt at `topology` when the clarification is also ambiguous" in flat
    assert "Persist only `single` or `stacked`. Never persist free text." in flat
    # `--auto` must not bypass the question.
    assert "unchanged under `--auto`" in topology


def test_plate_repair_topology_requires_run_branch_and_one_overlap_rule() -> None:
    topology = read("skills/plate/references/topology.md")
    repair = topology.split("## Repair-worktree topology", maxsplit=1)[1]
    flat = " ".join(repair.split())
    assert "The repair handoff must carry `run_branch`" in flat
    assert "Halt at `topology` when `run_branch` is absent" in flat
    assert "A missing field is not evidence of a deleted branch" in flat
    assert "git diff --name-only --find-renames" in repair
    assert "git diff --numstat" in flat
    assert "Count a rename as its changed lines only" in flat
    assert "Count a binary path as one changed line" in flat
    assert "git rev-parse --verify <run-branch>" in flat
    # Cook owns the harvest command. Plate routes to it rather than naming
    # cook.pyz, which the bundle-closure gate forbids in a plate document.
    assert "Cook owns the harvest command" in flat
    assert "cook/references/quality-gates.md" in flat
    assert "cook.pyz" not in repair
    # Never the non-existent `worktree_harvest` function.
    assert "worktree_harvest" not in repair


def test_plate_final_writing_gate_precedes_publication() -> None:
    skill = read("skills/plate/SKILL.md")
    durable = read("skills/plate/references/durable-writes.md")
    assert skill.index("Final writing gate") < skill.index("`just check`")
    assert "wiki-ingest" in durable
    assert "docs/adr/" in durable
    assert "{target, backend, verified}" in durable
    assert "read back" in durable.lower()
    assert "halt" in durable.lower()
    assert ".cheese" in durable and "unstaged" in durable
    assert "bottom/common branch" in durable


def test_plate_hard_gate_defines_its_context_and_status_matrix() -> None:
    """The `/hard-cheese` seam needs a validated context and every gate status."""
    skill = read("skills/plate/SKILL.md")
    durable = read("skills/plate/references/durable-writes.md")
    gate = skill.split("## Hard gate", maxsplit=1)[1].split("\n## ", maxsplit=1)[0]
    flat_gate = " ".join(gate.split())
    for field in ("artifacts", "inventory", "tracked_diff_digest", "gate"):
        assert f"`{field}`" in durable, field
    assert "Halt when a field is missing" in durable
    assert "Do not reuse a digest from an earlier state" in durable
    assert "tracked artifact diff digest" in flat_gate
    for status, response in (
        ("`PASS`", "Continue to publication"),
        ("`LOGGED`", "Record the logged findings"),
        ("`ERROR`", "Ask the user before you publish"),
        ("`FAILED`", "Halt at `quality gate`"),
    ):
        assert status in gate, status
        assert response in gate, response


def test_plate_loads_one_reference_at_a_time_in_a_named_sequence() -> None:
    skill = read("skills/plate/SKILL.md")
    section = skill.split("## Classify, then load one reference", maxsplit=1)[1]
    flat = " ".join(section.split())
    assert "Load one reference at a time" in flat
    assert "Load each reference alone. Close it before you load the next one." in flat
    topology = flat.index("Load `references/topology.md`")
    execution = flat.index("Load `references/ordinary-pr.md` for single topology")
    provider = flat.index("Load exactly one provider reference")
    assert topology < execution < provider
    # Stack inspection without a requested change belongs to `/gh`.
    assert "Create, sync, restack, submit, recover, or explicitly ship a stack" in skill
    assert "Route a stack inspection request without a requested change to `/gh`" in flat


def test_plate_routes_tools_and_reports_a_scannable_completion_record() -> None:
    skill = read("skills/plate/SKILL.md")
    assert "## Tool routing" in skill
    assert "Git and GitHub" in skill
    assert "code-intelligence backend" in skill
    assert "/wiki-ingest" in skill

    completion = skill.split("## Completion", maxsplit=1)[1]
    block = completion.split("```json\n", maxsplit=1)[1].split("\n```", maxsplit=1)[0]
    record = cast(dict[str, object], json.loads(block))
    assert set(record) == {
        "mode",
        "topology",
        "provider",
        "artifacts",
        "gate",
        "commits",
        "prs",
        "risk",
    }
    artifacts = cast(list[object], record["artifacts"])
    gate = cast(dict[str, object], record["gate"])
    assert record["mode"] == "new-pr"
    assert cast(dict[str, object], artifacts[0])["verified"] is True
    assert gate["result"] == "pass"
    assert "Topology preflight" in completion
    assert 'gate: {"command": "n/a", "result": "n/a"}' in completion
    assert "scripts/plate.pyz validate-publication" in completion
    assert "scripts/plate.pyz stack-tools" in skill


def test_plate_stack_references_preserve_absorbed_behavior_and_safety() -> None:
    bodies = {
        name: read(f"skills/plate/references/{name}.md")
        for name in ("gt", "git-town", "gh-stack")
    }
    # Each provider must prohibit the bare Git recovery command by name and
    # name its own continue/abort pair. A reference that merely mentions
    # `git rebase --continue` as the recovery path would satisfy a bare
    # substring check, so assert the prohibition and the replacement.
    prohibitions = {
        "gt": "A bare `git rebase --continue` is never the recovery path",
        "git-town": "A bare `git rebase --continue` is never correct",
        "gh-stack": "Do not run `git rebase --continue`.",
    }
    recoveries = {
        "gt": ("gt continue", "gt abort"),
        "git-town": ("git town continue", "git town undo"),
        "gh-stack": ("gh stack rebase --continue", "gh stack rebase --abort"),
    }
    for name, body in bodies.items():
        assert "git add -A" not in body
        assert "git add ." not in body
        assert "--no-verify" not in body
        assert "git commit --amend" not in body
        assert "git rev-parse --git-dir" in body
        assert ".git/" not in body
        recovery = body.split("## Conflict recovery", maxsplit=1)[1].split(
            "\n## ", maxsplit=1
        )[0]
        flat_recovery = " ".join(recovery.split())
        assert prohibitions[name] in flat_recovery, name
        for command in recoveries[name]:
            assert f"`{command}`" in flat_recovery, (name, command)
        assert "git rebase --continue" not in flat_recovery.replace(
            prohibitions[name], ""
        ), name

    graphite = bodies["gt"]
    for command in ("gt modify", "gt split", "gt absorb", "gt pop", "gt undo"):
        assert command in graphite
    for behavior in ("frozen", "gt unfreeze", "gt trunk --add", "--no-interactive"):
        assert behavior in graphite

    git_town = bodies["git-town"]
    for behavior in (
        "git town ship",
        "--prototype",
        "sync --all",
        "sync --detached",
        "sync --prune",
        "branchtype",
        "--non-interactive",
    ):
        assert behavior in git_town

    gh_stack = bodies["gh-stack"]
    for behavior in (
        "--prefix",
        "--numbered",
        "--remote",
        "submit --auto",
        "Generic error",
        "Invalid arguments",
    ):
        assert behavior in gh_stack


def test_gh_stack_enablement_is_preflighted_not_discovered_on_mutation() -> None:
    gh_stack = read("skills/plate/references/gh-stack.md")
    stacks = read("skills/plate/references/stacks.md")
    flat = " ".join(gh_stack.split())

    assert "no documented preflight" not in gh_stack
    assert 'gh api --include "repos/{owner}/{repo}/stacks"' in gh_stack
    assert 'gh api --include "repos/{owner}/{repo}/stacks"' in stacks
    assert "run it before the first stack mutation" in flat
    for status, verdict in (
        ("`2xx`", "Stacked PRs enabled"),
        ("`404`", "Repository enablement requirement"),
        ("`401`, `403`", "Authentication or authorization failure"),
    ):
        assert status in gh_stack
        assert verdict in gh_stack
    # Exit code 4 survives as the race/late-failure fallback, not the primary
    # enablement signal.
    assert "fallback for races and later remote failures" in flat
    assert "exit code 4 stays the fallback" in flat
    assert "| 4 | API/preview unavailable |" in gh_stack
    assert "`not-enabled` (preflight `404`)" in stacks


def test_plate_stack_flow_is_per_layer_and_metadata_is_resolved() -> None:
    skill = read("skills/plate/SKILL.md")
    stacks = read("skills/plate/references/stacks.md")
    provider = stacks.index("Select the configured provider")
    lineage = stacks.index("Create or adopt provider lineage")
    layer_gate = stacks.index("Run the final writing gate for that layer")
    submit = stacks.index("Submit the complete chain")
    assert provider < lineage < layer_gate < submit
    assert "explicit split boundaries" in stacks
    assert "bottom/common layer" in stacks
    assert "git rev-parse --git-dir" in stacks
    assert ".git/" not in stacks
    assert ".git/" not in skill
    # The per-layer transaction lives in the stack reference; the core body only
    # points at it, so the generic transaction is never mistaken for it.
    assert "Select the configured provider" not in skill
    assert "per-layer transaction in `references/stacks.md`" in skill


def test_plate_routing_guard_rejects_review_and_read_only_github_work() -> None:
    skill = read("skills/plate/SKILL.md")
    guard = skill.split("## Routing guard", maxsplit=1)[1].split("\n## ", maxsplit=1)[0]
    flat = " ".join(guard.split())
    # The guard runs before a mode is selected, so it precedes the mode table.
    assert skill.index("## Routing guard") < skill.index("## Classify, then load one reference")
    assert "never computes a review surface for its own sake" in flat
    assert "Review is `/age`" in flat
    assert "leaves `/plate` before any mode is selected" in flat
    assert "routing it here is a plate-owned failure" in flat
    assert "require explicit user authorization" in flat


def test_plate_mode_table_maps_each_mode_to_exactly_one_reference() -> None:
    skill = read("skills/plate/SKILL.md")
    table = skill.split("## Classify, then load one reference", maxsplit=1)[1]
    rows = [
        line
        for line in table.split("\n## ", maxsplit=1)[0].splitlines()
        if line.startswith("| ") and not line.startswith("| ---") and "| Mode |" not in line
    ]
    loads = {}
    for row in rows:
        cells = [cell.strip() for cell in row.strip("|").split("|")]
        assert len(cells) == 3, row
        mode, _trigger, load = cells
        targets: set[str] = set(cast(list[str], re.findall(r"references/([A-Za-z0-9_.\-]+\.md)", load)))
        assert len(targets) == 1, f"{mode} must name exactly one reference, got {targets}"
        target = targets.pop()
        assert (ROOT / "skills/plate/references" / target).is_file()
        loads[mode] = target

    assert loads == {
        "Commit-only": "durable-writes.md",
        "Topology preflight": "topology.md",
        "New PR": "topology.md",
        "Existing PR": "ordinary-pr.md",
        "Stack maintenance": "stacks.md",
    }
    assert "Do not read the others." in skill
    # Provider files are reached from stacks.md, never selected by the table.
    for provider in ("gt.md", "git-town.md", "gh-stack.md"):
        assert provider not in "".join(rows)


def test_plate_durable_write_sequence_is_canonical_and_op_shaped() -> None:
    durable = read("skills/plate/references/durable-writes.md")
    skill = read("skills/plate/SKILL.md")
    flat = " ".join(durable.split())
    sequence = durable.split("## Canonical write sequence", maxsplit=1)[1]
    fresh = sequence.index("Fresh tagged read")
    write = sequence.index("One stale-safe write")
    readback = sequence.index("Diff read-back")
    assert fresh < write < readback
    assert "Never reuse a tag, a line number, or a file body captured earlier" in flat
    assert "carries only the exact unique `old` string and its `new` replacement" in flat
    assert "never `start`/`end` line numbers" in flat
    assert "Mixing the two op shapes is a malformed write" in flat
    assert "a call-shape defect owned by this skill, not a backend outage" in flat
    assert "never retry with the stale tag" in flat
    assert "never fall back to a shell redirect or a host editor" in flat
    # The core body points at the sequence instead of restating it.
    assert "fresh tagged read, one stale-safe write, diff read-back" in " ".join(skill.split())
    assert "Canonical write sequence" not in skill


def test_plate_halt_vocabulary_is_fixed_and_splits_ownership() -> None:
    skill = read("skills/plate/SKILL.md")
    halting = skill.split("## Halting", maxsplit=1)[1].split("\n## ", maxsplit=1)[0]
    flat = " ".join(halting.split())
    steps = cast(
        list[str],
        re.findall(r"`([a-z/ ]+)`", flat.split("Name the step with exactly one of:")[1]),
    )
    assert steps[:7] == [
        "classify",
        "topology",
        "durable write",
        "quality gate",
        "stage/commit",
        "publish",
        "terminal validation",
    ]
    assert "Every halt names the mode, the failed step, and who owns the failure" in flat
    assert "**Plate-owned**" in halting
    assert "**Environment-owner**" in halting
    assert "Fix the call shape or the routing, then retry that step" in flat
    assert "Never retry it as if the call shape were wrong" in flat
    assert "never weaken a gate, stage unnamed paths, or skip read-back" in flat
    assert "halt at `quality gate`. Then fix the work" in flat
    # Prose and contract assertions only -- no telemetry backend.
    for backend in ("otel", "OpenTelemetry", "span", "metric", "emit "):
        assert backend not in halting


def test_plate_replay_evals_cover_malformed_writes_and_review_surface() -> None:
    evals = cast(
        dict[str, object], json.loads(read("skills/plate/evals/evals.json"))
    )
    cases = cast(list[dict[str, object]], evals["evals"])
    ids = [case["id"] for case in cases]
    assert len(ids) == len(set(ids))
    by_id = {case["id"]: case for case in cases}

    malformed = by_id[16]
    assert malformed["name"] == "malformed-durable-write"
    assert "replace_text" in cast(str, malformed["prompt"])
    expected = cast(str, malformed["expected_output"])
    assert "durable write" in expected
    assert "plate-owned" in expected
    assert "never start/end" in expected
    assert "fresh tagged read" in expected
    assert "diff read-back" in expected
    assert "backend outage" in expected

    review = by_id[17]
    assert review["name"] == "review-surface-request"
    surface = cast(str, review["expected_output"])
    assert "classify" in surface
    assert "plate-owned" in surface
    assert "/age" in surface
    assert "never computes a review surface for its own sake" in surface


def test_ultracook_preflights_parallel_publication_before_commits() -> None:
    # /ultracook retired to a stub; the preflight mechanics it used to
    # document now live in cook/SKILL.md's `## Fan pathway`, trimmed out to
    # cook/references/*.md.
    cook_dir = ROOT / "skills" / "cook"
    skill = read("skills/cook/SKILL.md") + "".join(
        p.read_text() for p in sorted((cook_dir / "references").glob("*.md"))
    )
    schema = read("skills/ultracook/references/manifest-schema.json")
    plan_schema = read("skills/ultracook/references/pr-plan-schema.json")
    planner = read("skills/ultracook/references/pr-planner-prompt.md")

    preflight = skill.index("Publication topology preflight")
    seed = skill.index("**Seed (coder).**")
    assert preflight < seed
    assert "before Phase 1 seed or any worker commit" in skill
    assert "persist `single` without asking" in skill
    assert "stacked is recommended or shape is ambiguous" in skill
    assert "do not ask twice" in skill
    assert '"plate_layout"' in schema
    assert '"single", "stacked"' in schema
    assert "explicit choice, cohesive-single inference, or user confirmation" in schema
    assert '"plate_layout"' in plan_schema
    assert '"required": ["plate_layout", "shape", "groups"]' in plan_schema
    assert "cannot override an explicit" in plan_schema
    assert "copy it exactly into the plan" in planner.lower()
    assert "owns the size gate" in planner
    assert "skills/plate/references/topology.md" in planner
    assert "~400" not in planner


def test_cure_open_pr_dispatch_obeys_plate_policy() -> None:
    cure_dir = ROOT / "skills" / "cure"
    cure = read("skills/cure/SKILL.md") + "".join(
        (cure_dir / "references" / f"{name}.md").read_text()
        for name in ("auto-mode", "selection", "post-pr-writeback")
    )
    assert "explicit topology choices and obviously cohesive work proceed without asking" in cure
    assert "stack-sized or ambiguous work asks before commit or branch-layout mutation" in cure


def test_plate_routes_review_to_age_from_both_sides() -> None:
    """The Plate-to-Age ownership edge, asserted on the producer and consumer."""
    skill = read("skills/plate/SKILL.md")
    age = read("skills/age/SKILL.md")
    evals = cast(dict[str, object], json.loads(read("skills/plate/evals/evals.json")))
    by_name = {
        cast(str, case["name"]): case
        for case in cast(list[dict[str, object]], evals["evals"])
    }

    # Producer: Plate refuses the review and names the owner.
    guard = skill.split("## Routing guard", maxsplit=1)[1].split("\n## ", maxsplit=1)[0]
    assert "`/plate` never performs code-quality review." in guard
    assert "It never computes a review surface for its own sake." in guard
    assert "Review is `/age`" in guard
    assert "Work for `/age` or `/gh` is a Plate-owned routing error" in skill

    # Consumer: Age owns the review and defaults to the current working diff.
    assert "name: age" in age
    assert "Review a diff, PR, branch, or path" in age
    assert "Review the current working diff." in age
    assert "Do not apply fixes. Route them to /cure." in age

    # The seam's failure mode halts at `classify`, not at a review verdict.
    surface = cast(str, by_name["review-surface-request"]["expected_output"])
    assert "Halts at classify" in surface
    assert "plate-owned" in surface
    assert "/age" in surface
    assert "never blending a quality verdict into the completion record" in surface


def test_plate_is_installed_and_routed() -> None:
    assert '"./skills/plate"' in read(".claude-plugin/plugin.json")
    assert " plate " in f" {read('scripts/install.sh')} "
    assert "`/plate`" in read("README.md")
    assert "`/plate`" in read("AGENTS.md")
    for path in (
        "skills/cure/SKILL.md",
        "skills/cook/SKILL.md",
        "skills/mold/SKILL.md",
        "skills/affinage/SKILL.md",
        "skills/ultracook/SKILL.md",
        "skills/ultracook/references/curd-prompt.md",
        "skills/ultracook/references/wiring-prompt.md",
        "skills/ultracook/references/pr-planner-prompt.md",
        "skills/cheese/SKILL.md",
        "skills/cheese/references/classification.md",
        "skills/cheese/references/coherence-check.md",
        "skills/cheese/references/handoff-gate.md",
    ):
        body = read(path)
        assert "/commit" not in body
        assert "/pr-stack" not in body
