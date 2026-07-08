"""Resolve-check gate: every skill directory ships wholesale (sibling installers
discover per-skill dirs only), so a relative markdown ref that only resolved
against the old repo-root `shared/` tree becomes a dangling link on install.
This walks the live `skills/**/*.md` source tree (not a staged copy) and
asserts every relative ref resolves from its own file's directory, plus that
no prose ref regresses to a repo-anchored path a wholesale-shipped skill
can't see.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SKILLS_ROOT = REPO_ROOT / "skills"

_MD_LINK_RE = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")
_BACKTICK_RE = re.compile(r"`([^`]+)`")
_PROSE_REF_RE = re.compile(r"^(?:\.\./)+[\w./-]+\.md(?:#[\w-]+)?$|^references/[\w./-]+\.md(?:#[\w-]+)?$")

# The six docs that used to live at repo-root shared/*.md before the
# cheese-kernel-shared-refs move; semantic-backends was inlined and deleted
# rather than relocated, but a regressed reference to it is equally dangling.
_FORMER_SHARED_NAMES = (
    "formatting",
    "handoff-gate",
    "harness-portability",
    "optional-plugins",
    "skill-authoring",
    "semantic-backends",
)
_SHARED_MD_RE = re.compile(
    r"(?:^|[(`\s])shared/(?:" + "|".join(_FORMER_SHARED_NAMES) + r")\.md"
)

# Owner-homed docs living inside one skill's references/ dir; a repo-anchored
# `skills/<owner>/references/<name>.md` prose ref only resolves for a full
# repo checkout, not a wholesale-installed sibling skill.
_OWNER_HOMED_NAMES = ("voice", "sub-agent-gate", "dimensions", "selection", "composition")
_OWNER_HOMED_RE = re.compile(
    r"skills/[\w-]+/references/(?:" + "|".join(_OWNER_HOMED_NAMES) + r")\.md"
)

# A moved doc referenced by its new repo-anchored path from inside a skill
# file is just as dangling on a wholesale install as the old shared/ form —
# skill files must cite it relative-from-current-file
# (`../cheese/references/<f>.md` or `../../cheese/references/<f>.md`), never
# `skills/cheese/references/<f>.md`. Checked across .md AND .json (a real
# instance of exactly this shape was found in manifest-schema.json).
_MOVED_REPO_ANCHORED_RE = re.compile(
    r"skills/cheese/references/(?:" + "|".join(_FORMER_SHARED_NAMES) + r")\.md"
)


def _skill_markdown_files() -> list[Path]:
    return sorted(SKILLS_ROOT.rglob("*.md"))


def _skill_json_files() -> list[Path]:
    return sorted(SKILLS_ROOT.rglob("*.json"))


def _relative_md_refs(text: str) -> list[str]:
    """Every relative markdown-link target and backticked relative-path prose
    ref in ``text``, with any `#fragment` (and ` § heading` prose suffix)
    stripped."""
    refs: list[str] = []
    for match in _MD_LINK_RE.finditer(text):
        target = match.group(1)
        if target.startswith(("http://", "https://", "mailto:", "#")):
            continue
        path = target.split("#", 1)[0]
        if path.endswith(".md"):
            refs.append(path)
    for match in _BACKTICK_RE.finditer(text):
        candidate = match.group(1).split(" § ", 1)[0]
        if _PROSE_REF_RE.match(candidate):
            refs.append(candidate.split("#", 1)[0])
    return refs


def test_relative_refs_resolve_in_skills_tree() -> None:
    """Every relative markdown ref under skills/**/*.md must resolve from its
    own file's directory — the wholesale-per-skill-dir install path has no
    repo-root fallback to catch a dangling ref."""
    problems: list[str] = []
    for md in _skill_markdown_files():
        for ref in _relative_md_refs(md.read_text(encoding="utf-8")):
            if not (md.parent / ref).resolve().is_file():
                problems.append(f"{md.relative_to(REPO_ROOT)} -> {ref}")
    assert not problems, "unresolved refs in skills/:\n" + "\n".join(problems)


def test_no_former_shared_md_repo_anchored_refs() -> None:
    """No skills/ doc may reference the retired shared/*.md tree by its old
    repo-root path — those docs moved under skills/cheese/references/ (or, for
    semantic-backends, were inlined and deleted)."""
    problems: list[str] = []
    for md in _skill_markdown_files():
        text = md.read_text(encoding="utf-8")
        for match in _SHARED_MD_RE.finditer(text):
            problems.append(f"{md.relative_to(REPO_ROOT)}: {match.group(0).strip()}")
    assert not problems, "repo-anchored shared/*.md refs found:\n" + "\n".join(problems)


def test_no_owner_homed_repo_anchored_prose_refs() -> None:
    """No skills/ doc may reference another skill's owner-homed reference doc
    by its full repo-anchored path — that path doesn't exist once each skill
    ships as an isolated directory. Cross-skill refs must use a relative form
    (e.g. `../age/references/voice.md`) instead."""
    problems: list[str] = []
    for md in _skill_markdown_files():
        text = md.read_text(encoding="utf-8")
        for match in _OWNER_HOMED_RE.finditer(text):
            problems.append(f"{md.relative_to(REPO_ROOT)}: {match.group(0)}")
    assert not problems, "repo-anchored owner-homed refs found:\n" + "\n".join(problems)



def test_no_moved_doc_repo_anchored_refs_in_skills_tree() -> None:
    """No file inside skills/ (markdown or JSON) may cite a moved doc by its
    new repo-anchored path (`skills/cheese/references/<f>.md`) — that only
    resolves against a full repo checkout, not a wholesale-installed sibling
    skill directory. Skill files must use the sibling-relative form instead
    (`../cheese/references/<f>.md` or `../../cheese/references/<f>.md`).
    Regression case: manifest-schema.json shipped exactly this repo-anchored
    form, undetected by the markdown-only checks above."""
    problems: list[str] = []
    for path in [*_skill_markdown_files(), *_skill_json_files()]:
        text = path.read_text(encoding="utf-8")
        for match in _MOVED_REPO_ANCHORED_RE.finditer(text):
            problems.append(f"{path.relative_to(REPO_ROOT)}: {match.group(0)}")
    assert not problems, "repo-anchored moved-doc refs found:\n" + "\n".join(problems)