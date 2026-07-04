r"""Guard against bare ``cheez-*`` wildcard tokens corrupting Markdown emphasis.

``scripts/gen_docs.py`` mirrors these sources verbatim into the MkDocs site. A
bare ``cheez-*`` in prose has its ``*`` parsed as an emphasis delimiter by
Python-Markdown: two in one paragraph italicise the span between them, and one
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
    """Every markdown source the MkDocs site renders.

    Covers both what gen_docs.py mirrors verbatim (root docs, SKILL.md bodies,
    references, shared contracts) and the hand-authored ``docs/*.md`` pages that
    mkdocs renders directly — a bare ``cheez-*`` corrupts emphasis in either.
    """
    files = [
        REPO_ROOT / "README.md",
        REPO_ROOT / "CONTRIBUTING.md",
        REPO_ROOT / "SECURITY.md",
        REPO_ROOT / "CODE_OF_CONDUCT.md",
    ]
    files += sorted((REPO_ROOT / "docs").glob("*.md"))
    files += sorted((REPO_ROOT / "skills").glob("*/SKILL.md"))
    files += sorted((REPO_ROOT / "skills").glob("*/references/*.md"))
    files += sorted((REPO_ROOT / "shared").glob("*.md"))
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
    assert not _hazards("the cheez-* skills require tilth.\n")


def test_detector_ignores_legit_bold_after_token():
    # `cheez-**bold**` is an intended bold run, not the `cheez-***` corruptor.
    assert not _hazards("use cheez-**bold** here\n")


def test_detector_ignores_backticked_tokens():
    assert not _hazards("use `cheez-*` and `cheez-*` freely\n")


def test_cheez_skills_accept_equivalent_native_backends_without_blind_shell_fallbacks():
    docs = [
        REPO_ROOT / "README.md",
        REPO_ROOT / "AGENTS.md",
        REPO_ROOT / ".hallouminate/wiki/tooling.md",
        REPO_ROOT / "skills/cheez-read/SKILL.md",
        REPO_ROOT / "skills/cheez-search/SKILL.md",
        REPO_ROOT / "skills/cheez-write/SKILL.md",
    ]
    combined = "\n".join(path.read_text(encoding="utf-8") for path in docs)

    assert "tilth MCP is the preferred implementation, not the only valid one" in combined
    assert "semantic source-code backend, not tilth specifically" in combined
    assert "Plain shell fallbacks still fail the contract" in combined
    assert "mcp__tilth__tilth_files" in combined
    assert "mcp__tilth__tilth_edit" in combined
    assert "AST Grep, LSP" in combined
    assert "Requires tilth MCP server" not in combined
    assert "require tilth MCP by design" not in combined
