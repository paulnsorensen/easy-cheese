"""Contract tests for shared workflow documentation."""

from __future__ import annotations

import re
import shutil
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]

def test_shared_source_routing_contract_is_linked_and_complete():
    routing = REPO_ROOT / "skills/cheese/references/code-intelligence-routing.md"
    body = routing.read_text(encoding="utf-8")

    assert "Route by question or edit shape" in body
    assert "LSP" in body and "Serena" in body and "code action" in body
    assert "tilth" in body and "semantic source-code backend" in body
    assert "AST search or rewrite" in body and "`sg`" in body
    assert "Search" in body and "Fresh bounded read" in body and "Stale-safe write" in body
    assert "backend-family contracts" in body
    assert "precision loss" in body

    routed_docs = (
        "skills/age/SKILL.md",
        "skills/affinage/SKILL.md",
        "skills/briesearch/SKILL.md",
        "skills/cheese/SKILL.md",
        "skills/cook/SKILL.md",
        "skills/culture/SKILL.md",
        "skills/cure/SKILL.md",
        "skills/melt/SKILL.md",
        "skills/mold/SKILL.md",
        "skills/pasteurize/SKILL.md",
        "skills/press/SKILL.md",
        "skills/ultracook/SKILL.md",
    )
    for path in routed_docs:
        assert "code-intelligence-routing.md" in (REPO_ROOT / path).read_text(encoding="utf-8"), path


def test_documented_single_workflow_install_resolves_shared_routing_contract(tmp_path):
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    _, heading, tail = readme.partition("Install one workflow skill")
    assert heading, "README must document workflow-skill dependencies"
    section, next_heading, _ = tail.partition("Pin both skills")
    assert next_heading

    skills = re.findall(
        r"gh skill install paulnsorensen/easy-cheese ([\w-]+)", section
    )
    assert skills == ["cheese", "cook"]

    installed = tmp_path / "skills"
    for skill in skills:
        shutil.copytree(REPO_ROOT / "skills" / skill, installed / skill)

    cook = installed / "cook" / "SKILL.md"
    links = re.findall(
        r"\]\(([^)]+code-intelligence-routing\.md)\)",
        cook.read_text(encoding="utf-8"),
    )
    assert links
    for link in links:
        assert (cook.parent / link).resolve().is_file(), link


def test_harness_portability_reference_is_linked_from_workflow_docs():
    docs = [
        REPO_ROOT / "skills/cheese/references/formatting.md",
        REPO_ROOT / "skills/cook/SKILL.md",
        REPO_ROOT / "skills/press/SKILL.md",
        REPO_ROOT / "skills/age/SKILL.md",
        REPO_ROOT / "skills/cure/SKILL.md",
        # skills/ultracook/SKILL.md dropped: retired to a short redirect
        # stub, no longer a harness-dispatching workflow doc in its own
        # right (its mechanics — and this portability reference — moved
        # into skills/cook/SKILL.md, already in this list).
        REPO_ROOT / "skills/mold/SKILL.md",
        REPO_ROOT / "skills/cheese/SKILL.md",
        REPO_ROOT / "skills/affinage/SKILL.md",
        REPO_ROOT / "skills/hard-cheese/SKILL.md",
        REPO_ROOT / "skills/pasteurize/SKILL.md",
    ]

    for path in docs:
        text = path.read_text(encoding="utf-8")
        if path.name == "formatting.md":
            assert "harness-portability.md" in text
            assert "Portable host-capability wording" in text
        elif path == REPO_ROOT / "skills/cheese/SKILL.md":
            assert "references/harness-portability.md" in text, path
            assert "slash commands are host renderings, not the control model" in text, path
        else:
            assert "cheese/references/harness-portability.md" in text, path
            assert "slash commands are host renderings, not the control model" in text, path



    portable_examples = {
        # /ultracook retired to a stub; portable mode, tracking, and worktree
        # commands now live one hop under cook's fan-pathway reference. Legacy
        # phase-state and decomposition commands are intentionally not live.
        REPO_ROOT / "skills/cook/SKILL.md": (
            "cook.pyz artifact-path",
            "cook.pyz read_handoff_slug",
            "cook.pyz mode",
            "cook.pyz milknado",
            "cook.pyz worktree create",
            "cook.pyz worktree harvest",
            "cook.pyz worktree teardown",
        ),
        REPO_ROOT / "skills/age/SKILL.md": (
            "age.pyz read_handoff_slug",
            "age.pyz write_handoff_artifact",
            "age.pyz html-report",
        ),
        REPO_ROOT / "skills/affinage/SKILL.md": (
            "python3 skills/affinage/scripts/affinage.pyz pr-status",
            "python3 skills/affinage/scripts/affinage.pyz post-reply",
        ),
        REPO_ROOT / "skills/hard-cheese/SKILL.md": (
            "python3 skills/hard-cheese/scripts/hard-cheese.pyz freshness-check",
            "python3 skills/hard-cheese/scripts/hard-cheese.pyz append-attempt",
        ),
        REPO_ROOT / "skills/mold/SKILL.md": (
            "mold.pyz artifact-path",
            "mold.pyz gate-graph",
        ),
        REPO_ROOT / "skills/pasteurize/SKILL.md": (
            "python3 skills/pasteurize/scripts/pasteurize.pyz repro-rerun",
            "python3 skills/pasteurize/scripts/pasteurize.pyz debug-tag-sweep",
        ),
    }

    for path, snippets in portable_examples.items():
        # A skill's portable invocations may live in the SKILL.md body or in any
        # of its routed references/ files -- the body is token-budgeted, so
        # worked command examples legitimately sit one hop out.
        text = path.read_text(encoding="utf-8")
        for ref in sorted((path.parent / "references").glob("*.md")):
            text += ref.read_text(encoding="utf-8")
        for snippet in snippets:
            assert snippet in text, path

    for path in (
        REPO_ROOT / "skills/affinage/SKILL.md",
        REPO_ROOT / "skills/hard-cheese/SKILL.md",
        REPO_ROOT / "skills/pasteurize/SKILL.md",
    ):
        assert "${CLAUDE_SKILL_DIR}/scripts/" not in path.read_text(encoding="utf-8"), path


def test_harness_portability_reference_covers_the_portability_contract():
    body = (REPO_ROOT / "skills/cheese/references/harness-portability.md").read_text(encoding="utf-8")

    assert "Helper resolution" in body
    assert "repo-local" in body and "bundled" in body and "environment variable" in body
    assert "sub-agent dispatch" in body
    assert "Anthropic Claude Code: `Agent(...)`" in body
    assert "Codex: host-exposed sub-agent capability" in body
    assert "`collaboration.spawn_agent`" in body
    assert "multi_agent_v1.spawn_agent" not in body
    assert "OMP: `task(...)`" in body
    assert "OMP / Codex" not in body and "Codex-style" not in body
    assert "GitHub operations" in body
    assert "host GitHub primitive when the harness exposes one" in body
    assert "`gh` CLI as the fallback transport" in body
    assert "Handoff transitions" in body
    assert "Slash commands are presentation, not the control model." in body
    assert "status" in body and "next" in body and "artifact" in body and "explicit dispatch data" in body


def test_question_routing_is_native_first_and_lossless():
    questions = (REPO_ROOT / "skills/cheese/references/ask-user-question.md").read_text(
        encoding="utf-8"
    )
    sources = (
        REPO_ROOT / "skills/cheese/references/ask-user-question-sources.md"
    ).read_text(encoding="utf-8")
    portability = (REPO_ROOT / "skills/cheese/references/harness-portability.md").read_text(
        encoding="utf-8"
    )
    gate = (REPO_ROOT / "skills/cheese/references/handoff-gate.md").read_text(encoding="utf-8")

    # Ownership stays explicit: generic transport lives in one shared reference.
    assert "ask-user-question.md" in portability
    assert "handoff-gate.md" in portability
    assert "ask-user-question.md" in gate
    assert "AskUserQuestion" not in portability
    assert "| Claude Code |" not in gate

    # Handoff records project losslessly into the generic question schema.
    for required in (
        "source_skill: /cook",
        "**Source skill**",
        "id: post-cook-next-step",
        "prompt: What should happen next?",
        "recommended: harden-tests",
        "multi: false",
        "description: Strengthen regression coverage before review.",
    ):
        assert required in gate
    assert "question.id = handoff_gate.id" in gate
    assert "question.options = handoff_gate.options" in gate
    assert "keyed by option id" in gate

    # Four standard semantic options are a menu design, never a transport cap.
    assert "four options by design, not a host or button cap" in gate
    assert "every gate-specific alternative" in gate
    assert "four-option cap" not in gate
    assert "stays as prose plus the free-form `Other` path" not in gate

    # Hard-wrapped prose compares on flattened whitespace.
    questions_flat = " ".join(questions.split())
    sources_flat = " ".join(sources.split())

    # Runtime discovery reads the active tool list, never a lookup table.
    assert "richest callable structured question primitive" in questions_flat
    assert "visible in your active tool list" in questions_flat
    assert "never consult a harness lookup table" in questions_flat
    assert "advertised question and option capacities" in questions_flat
    assert "Runtime capability detection always wins over the wrapper or provider name." in questions_flat
    assert "selected underlying agent or provider" in questions_flat

    # The runtime doc carries no per-harness case statement.
    assert "| Claude Code |" not in questions
    assert "| --- |" not in questions
    assert "AskUserQuestion" not in questions
    assert "maintainer evidence, not runtime instructions" in questions_flat
    assert "ask-user-question-sources.md" in questions
    assert "Do not read that appendix to answer a question" in questions_flat

    # Behavioral caveats capability detection cannot infer stay in the runtime doc.
    assert "Caveats that capability detection alone cannot infer" in questions_flat
    assert "active tool list and current collaboration mode both allow it" in questions_flat
    assert "If an active" in questions_flat
    assert "2-3 explicit choices" in questions_flat
    assert "four-option" in questions_flat
    assert "2-3 explicit-choice limit" not in questions_flat
    assert "Codex `request_user_input` is the known case" in questions_flat
    assert "JSON/print or another non-interactive mode must use numbered text" in questions_flat
    assert "auto-select a blocking approval or state-changing choice" in questions_flat
    assert "not a general assistant-to-user question primitive" in questions_flat

    # Every rendering preserves the complete semantic question.
    assert "Never merge, hide, or drop options" in questions_flat
    assert "fallback must enumerate every option" in questions_flat
    for required in (
        "recommended choice",
        "every option's effect or tradeoff",
        "free-form `Other`",
        "recommended option's description",
        "omit the `Recommended:` line",
        "displayed 1-based ordinal",
    ):
        assert required in questions_flat

    # Per-harness citations live in the maintainer appendix, off the runtime path.
    assert "Maintainer appendix" in sources
    assert "Agents do not read this file at runtime" in sources_flat
    for harness in (
        "Claude Code",
        "Codex / OpenAI app-server",
        "Conductor",
        "OpenCode",
        "Pi",
        "OMP / Oh My Pi",
        "Emdash / Em Dash",
        "Cursor CLI / ACP",
    ):
        assert f"| {harness} |" in sources

    # Pi needs a loaded extension; OMP owns a distinct interactive built-in.
    assert "visibly loaded and callable extension tool" in sources
    assert "`ctx.hasUI`" in sources
    assert "Markdown skill cannot call `ctx.ui` directly" in sources
    assert "interactive-only built-in" in sources
    assert "`id`, `question`, and `options[]`" in sources
    assert "`Other` is automatic" in sources

    # Emdash is a provider host, not another universal question schema.
    assert "does not define one universal question API" in sources
    assert "selected provider's advertised primitive" in sources

    # Nothing routes an agent to the appendix at runtime.
    assert "ask-user-question-sources.md" not in portability
    assert "ask-user-question-sources.md" not in gate

    # Generic batching, defaults, and answer normalization stay with transport.
    assert "Ask one decision by default" in questions
    assert "at most three related questions" in questions
    assert "Never auto-resolve a blocking approval" in questions
    assert "Normalize the answer" in questions
    assert "If the answer is ambiguous" in questions


@pytest.mark.parametrize(
    "skill",
    (
        "affinage",
        "age",
        "cheese",
        "cook",
        "culture",
        "cure",
        "melt",
        "mold",
        "pasteurize",
        "press",
    ),
)
def test_core_workflow_question_sites_reference_shared_handoff_gate(skill: str):
    body = (REPO_ROOT / f"skills/{skill}/SKILL.md").read_text(encoding="utf-8")

    assert "handoff-gate.md" in body


def test_briesearch_clarifying_questions_reference_shared_question_transport():
    body = (REPO_ROOT / "skills/briesearch/SKILL.md").read_text(encoding="utf-8")

    assert "ask-user-question.md" in body
    assert "handoff-gate.md" not in body


def test_core_cheese_questions_use_the_shared_handoff_gate():
    cheese = (REPO_ROOT / "skills/cheese/SKILL.md").read_text(encoding="utf-8")

    assert "ask one clarifying question through the host routing guide" in cheese
    assert "references/handoff-gate.md" in cheese
    assert "Tier 3 blocks on a single targeted host-routed question" in cheese
    assert "With `--safe`, issue a handoff gate" in cheese
    assert "cross-harness post-selection dispatch contract" in cheese
    assert "Codex-safe" not in cheese


def test_wheypoint_git_provenance_is_capability_based_and_optional():
    body = (REPO_ROOT / "skills/wheypoint/SKILL.md").read_text(encoding="utf-8")

    assert "callable, read-only git inspection capability" in body
    assert "git status --short --branch" in body
    assert "git rev-parse --short HEAD" in body
    assert "branch and short commit" in body
    assert "Omit the field when git inspection is unavailable" in body
    assert "Bash(git" not in body
    assert "grant" not in body.lower()


def test_router_and_wheypoint_do_not_assume_claude_native_tools():
    for relative in ("skills/cheese/SKILL.md", "skills/wheypoint/SKILL.md"):
        frontmatter = (REPO_ROOT / relative).read_text(encoding="utf-8").split("---", 2)[1]
        for claude_tool in ("AskUserQuestion", "Read", "Glob", "Task", "Agent"):
            assert claude_tool not in frontmatter, f"{relative} assumes {claude_tool}"


def test_ultracook_spawn_reference_requires_fresh_context_or_halts():
    body = (REPO_ROOT / "skills/ultracook/references/spawn-primitive-reference.md").read_text(
        encoding="utf-8"
    )

    assert 'fork_turns: "none"' in body
    assert "halt `/ultracook` and recommend `/cook --auto`" in body
    assert "same context) instead" not in body
