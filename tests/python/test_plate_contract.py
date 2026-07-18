from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def read(path: str) -> str:
    return (ROOT / path).read_text()


def test_plate_owns_commit_stack_and_review_shape_policy() -> None:
    skill = read("skills/plate/SKILL.md")
    assert "name: plate" in skill
    assert "\nmodel:" not in skill
    assert "commit-only" in skill.lower()
    assert "cohesive review unit" in skill
    assert "proceed without asking" in skill
    assert "independently reviewable ordered" in skill
    assert "Do not use line-count or file-count thresholds" in skill
    assert "explicit user choice" in skill
    assert "It is authoritative" in skill
    assert "genuinely ambiguous" in skill
    assert "unchanged under `--auto`" in skill
    assert "before any commit" in skill
    assert "../cheese/references/ask-user-question.md" in skill
    assert "Existing PR" in skill
    assert "do not ask" in skill


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


def test_plate_stack_references_preserve_absorbed_behavior_and_safety() -> None:
    bodies = {
        name: read(f"skills/plate/references/{name}.md")
        for name in ("gt", "git-town", "gh-stack")
    }
    for body in bodies.values():
        assert "git add -A" not in body
        assert "git add ." not in body
        assert "--no-verify" not in body
        assert "git commit --amend" not in body
        assert "git rebase --continue" in body
        assert "git rev-parse --git-dir" in body
        assert ".git/" not in body

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


def test_plate_stack_flow_is_per_layer_and_metadata_is_resolved() -> None:
    skill = read("skills/plate/SKILL.md")
    provider = skill.index("Select the configured provider")
    lineage = skill.index("Create or adopt provider lineage")
    layer_gate = skill.index("Run the final writing gate for that layer")
    submit = skill.index("Submit the complete chain")
    assert provider < lineage < layer_gate < submit
    assert "explicit split boundaries" in skill
    assert "bottom/common layer" in skill
    assert "git rev-parse --git-dir" in skill
    assert ".git/" not in skill


def test_ultracook_preflights_parallel_publication_before_commits() -> None:
    skill = read("skills/ultracook/SKILL.md")
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
    assert "line-count or file-count thresholds" in planner
    assert "~400" not in planner


def test_cure_open_pr_dispatch_obeys_plate_policy() -> None:
    cure = read("skills/cure/SKILL.md")
    assert "explicit topology choices and obviously cohesive work proceed without asking" in cure
    assert "stack-sized or ambiguous work asks before commit or branch-layout mutation" in cure


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
        "skills/cheez-read/SKILL.md",
        "skills/cheez-search/SKILL.md",
    ):
        body = read(path)
        assert "/commit" not in body
        assert "/pr-stack" not in body
