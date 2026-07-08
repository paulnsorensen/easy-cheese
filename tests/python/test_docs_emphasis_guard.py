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
    assert "Codex: `multi_agent_v1.spawn_agent`" in body
    assert "OMP: `task(...)`" in body
    assert "OMP / Codex" not in body and "Codex-style" not in body
    assert "GitHub operations" in body
    assert "host GitHub primitive when the harness exposes one" in body
    assert "`gh` CLI as the fallback transport" in body
    assert "Handoff transitions" in body
    assert "Slash commands are presentation, not the control model." in body
    assert "status" in body and "next" in body and "artifact" in body and "explicit dispatch data" in body
