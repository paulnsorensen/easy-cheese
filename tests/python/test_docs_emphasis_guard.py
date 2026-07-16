r"""Guard against bare ``cheez-*`` wildcard tokens corrupting Markdown emphasis.

``scripts/gen_docs.py`` mirrors these sources into the Starlight docs site. A
bare ``cheez-*`` in prose has its ``*`` parsed as an emphasis delimiter by
Markdown renderers: two in one paragraph italicise the span between them, and one
immediately before a ``**`` close (``cheez-***``) leaks the ``*`` out of the
bold. Both render wrong on the docs site (confirmed by building it). The fix is
to wrap the token in inline code (```` `cheez-*` ````) or escape it
(``cheez-\*``). This test fails if a regression reintroduces the bare hazard.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]

FENCE_RE = re.compile(r"```.*?```", re.S)
INLINE_CODE_RE = re.compile(r"`[^`\n]*`")
BARE_TOKEN = "cheez-*"
# The corruptor is the `cheez-*` glob's `*` abutting a closing `**` run, i.e.
# three asterisks (`cheez-***`). A legit `cheez-**bold**` (two asterisks opening
# an intended bold) must NOT match.
COLLISION = "cheez-***"


def _rendered_markdown() -> list[Path]:
    """Every markdown source the Starlight site renders or mirrors.

    Covers both what gen_docs.py mirrors verbatim (root docs, SKILL.md bodies,
    references, shared contracts) and the hand-authored Starlight homepage — a
    bare ``cheez-*`` corrupts emphasis in either.
    """
    files = [
        REPO_ROOT / "README.md",
        REPO_ROOT / "CONTRIBUTING.md",
        REPO_ROOT / "SECURITY.md",
        REPO_ROOT / "CODE_OF_CONDUCT.md",
        REPO_ROOT / "src" / "content" / "docs" / "index.md",
    ]
    files += sorted((REPO_ROOT / "skills").glob("*/SKILL.md"))
    files += sorted((REPO_ROOT / "skills").glob("*/references/*.md"))
    return [f for f in files if f.exists()]


def _strip_code(text: str) -> str:
    """Blank out code spans (backticked tokens are exempt) but keep line count."""
    text = FENCE_RE.sub(lambda m: "\n" * m.group(0).count("\n"), text)
    return INLINE_CODE_RE.sub("", text)


def _hazards(text: str) -> list[tuple[int, str]]:
    """Return (paragraph-start-line, snippet) for each corrupting paragraph."""
    hazards: list[tuple[int, str]] = []
    para: list[str] = []
    start = 0

    def flush() -> None:
        if not para:
            return
        blob = " ".join(para)
        if blob.count(BARE_TOKEN) >= 2 or COLLISION in blob:
            hazards.append((start, blob.strip()[:120]))

    for i, line in enumerate(_strip_code(text).splitlines(), 1):
        if line.strip():
            if not para:
                start = i
            para.append(line)
        else:
            flush()
            para = []
    flush()
    return hazards


def test_no_bare_cheez_star_emphasis_hazard():
    offenders: list[str] = []
    for f in _rendered_markdown():
        for line, snippet in _hazards(f.read_text(encoding="utf-8")):
            offenders.append(f"{f.relative_to(REPO_ROOT)}:{line}  {snippet!r}")
    assert not offenders, (
        "Bare `cheez-*` corrupts Markdown emphasis in the docs build; wrap each "
        "occurrence in backticks (`cheez-*`) or escape it (cheez-\\*):\n"
        + "\n".join(offenders)
    )


def test_detector_flags_paired_tokens():
    # Two bare tokens in one paragraph -> italic span between them.
    assert _hazards("use cheez-* skills, not cheez-* fallbacks\n") == [
        (1, "use cheez-* skills, not cheez-* fallbacks")
    ]


def test_detector_flags_bold_collision():
    # cheez-* immediately before a `**` close -> the `*` leaks out of the bold.
    assert _hazards("**goes through cheez-***.\n") == [(1, "**goes through cheez-***.")]


def test_detector_ignores_single_bare_token():
    # A lone cheez-* followed by whitespace stays literal in the render.
    assert not _hazards("the cheez-* skills prefer tilth.\n")


def test_detector_ignores_legit_bold_after_token():
    # `cheez-**bold**` is an intended bold run, not the `cheez-***` corruptor.
    assert not _hazards("use cheez-**bold** here\n")


def test_detector_ignores_backticked_tokens():
    assert not _hazards("use `cheez-*` and `cheez-*` freely\n")


def test_cheez_skills_accept_equivalent_native_backends_without_blind_shell_fallbacks():
    docs = [
        REPO_ROOT / "README.md",
        REPO_ROOT / "AGENTS.md",
        REPO_ROOT / ".github/copilot-instructions.md",
        REPO_ROOT / ".hallouminate/wiki/tooling.md",
        REPO_ROOT / "skills/cheez-read/SKILL.md",
        REPO_ROOT / "skills/cheez-search/SKILL.md",
        REPO_ROOT / "skills/cheez-write/SKILL.md",
    ]
    combined = "\n".join(path.read_text(encoding="utf-8") for path in docs)

    # Shape contract: route by question/edit shape, with tilth as the example backend.
    assert "source-code backend contract" in combined
    assert "type-grounded" in combined and "LSP" in combined and "code actions" in combined
    assert "sg" in combined and "codemods" in combined
    assert "anchored" in combined and "anchors" in combined and "tilth" in combined
    assert "fallback evidence only" in combined

    # Live tilth tool identifiers must be documented (these are what the MCP exposes).
    assert "mcp__tilth__tilth_write" in combined
    assert "mcp__tilth__tilth_list" in combined

    # Renamed-away identifiers must never reappear — the MCP does not expose them.
    assert "tilth_edit" not in combined
    assert "tilth_files" not in combined
    assert "hard-fail without it" not in combined



def test_harness_portability_reference_is_linked_from_workflow_docs():
    docs = [
        REPO_ROOT / "skills/cheese/references/formatting.md",
        REPO_ROOT / "skills/cook/SKILL.md",
        REPO_ROOT / "skills/press/SKILL.md",
        REPO_ROOT / "skills/age/SKILL.md",
        REPO_ROOT / "skills/cure/SKILL.md",
        REPO_ROOT / "skills/ultracook/SKILL.md",
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
        REPO_ROOT / "skills/cook/SKILL.md": (
            "shared/scripts/artifact_path.py",
            "fallback",
        ),
        REPO_ROOT / "skills/age/SKILL.md": (
            "shared/scripts/read_handoff_slug.py",
            "shared/scripts/write_handoff_artifact.py",
            "fallback",
            "src/age/age-html-report.py",
        ),
        REPO_ROOT / "skills/ultracook/SKILL.md": (
            "shared/scripts/artifact_path.py",
            "shared/scripts/read_handoff_slug.py",
            "python3 skills/ultracook/scripts/ultracook.pyz phase_decision",
            "fallback",
            "python3 skills/ultracook/scripts/ultracook.pyz validate_decomposition",
            "python3 skills/ultracook/scripts/ultracook.pyz mode",
            "python3 skills/ultracook/scripts/ultracook.pyz milknado",
            "python3 skills/ultracook/scripts/ultracook.pyz worktree create",
            "python3 skills/ultracook/scripts/ultracook.pyz worktree harvest",
            "python3 skills/ultracook/scripts/ultracook.pyz worktree teardown",
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
            "python3 skills/mold/scripts/mold.pyz artifact-path",
            "python3 skills/mold/scripts/mold.pyz gate-graph",
        ),
        REPO_ROOT / "skills/pasteurize/SKILL.md": (
            "python3 skills/pasteurize/scripts/pasteurize.pyz repro-rerun",
            "python3 skills/pasteurize/scripts/pasteurize.pyz debug-tag-sweep",
        ),
    }

    for path, snippets in portable_examples.items():
        text = path.read_text(encoding="utf-8")
        for snippet in snippets:
            assert snippet in text, path

    for path in (
        REPO_ROOT / "skills/affinage/SKILL.md",
        REPO_ROOT / "skills/hard-cheese/SKILL.md",
        REPO_ROOT / "skills/mold/SKILL.md",
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
    assert "Runtime capability detection always wins over the wrapper or provider name." in questions
    assert "selected underlying agent or provider" in questions_flat

    # The runtime doc carries no per-harness case statement.
    assert "| Claude Code |" not in questions
    assert "| --- |" not in questions
    assert "AskUserQuestion" not in questions
    assert "maintainer evidence, not runtime instructions" in questions_flat
    assert "ask-user-question-sources.md" in questions
    assert "Do not read that appendix to answer a question" in questions_flat

    # Behavioral caveats capability detection cannot infer stay in the runtime doc.
    assert "Caveats that capability detection alone cannot infer" in questions
    assert "active tool list and current collaboration mode both allow it" in questions_flat
    assert "If an active" in questions
    assert "2-3 explicit choices" in questions_flat
    assert "four-option" in questions
    assert "2-3 explicit-choice limit" not in questions_flat
    assert "auto-select a blocking approval or state-changing choice" in questions_flat
    assert "not a general assistant-to-user question primitive" in questions_flat

    # Every rendering preserves the complete semantic question.
    assert "Never merge, hide, or drop options" in questions
    assert "fallback must enumerate every option" in questions
    for required in (
        "recommended choice",
        "every option's effect or tradeoff",
        "free-form `Other`",
        "recommended option's description",
        "omit the `Recommended:` line",
        "displayed 1-based ordinal",
    ):
        assert required in questions

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
