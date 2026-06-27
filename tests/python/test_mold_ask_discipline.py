"""Regression guard for RC1 of the mold-ask-not-lean redesign.

`/mold` (and its `/culture` twin) used to instruct: ask the *smallest useful
question* while contributing at *maximum useful depth*. On a strong model that
sentence backfires — it licenses the agent to minimise asking and maximise its
own confident output, i.e. to *lean* instead of *ask*. RC1 reworded both consumer
skills so asking the user is primary (spec: mold-ask-not-lean § Goals RC1, and the
quality gate "SKILL.md:19 / culture SKILL.md:33 no longer contain the phrase").

This guard fails if either half of the anti-pattern phrasing creeps back into the
two files the spec scoped the reword to. The shared voice kernel
(`skills/age/references/voice.md`) is deliberately NOT checked: it is the kernel
that legitimately defines the smallest-question / maximum-depth axis distinction
and was out of RC1's change scope. The regression guarded here is the *consumer*
skills re-adopting the self-defeating sentence, not the kernel keeping its axis.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCOPED_FILES = (
    REPO_ROOT / "skills" / "mold" / "SKILL.md",
    REPO_ROOT / "skills" / "culture" / "SKILL.md",
)

# The two halves of the self-defeating sentence RC1 removed.
ANTIPATTERN = re.compile(r"maximum useful depth|smallest[ -]useful[ -]question", re.I)
# RC1's positive intent: asking the user is the primary move.
ASKING_PRIMARY = re.compile(r"ask(?:ing)? the user", re.I)


def test_scoped_files_exist() -> None:
    missing = [str(p) for p in SCOPED_FILES if not p.exists()]
    assert not missing, f"RC1-scoped files moved or renamed: {missing}"


def test_no_lean_antipattern_phrase() -> None:
    offenders: list[str] = []
    for path in SCOPED_FILES:
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if ANTIPATTERN.search(line):
                offenders.append(f"{path.relative_to(REPO_ROOT)}:{n}: {line.strip()}")
    assert not offenders, (
        "RC1 anti-pattern phrasing reintroduced (asking minimised / agent output "
        "maximised) — reword so asking the user is primary:\n" + "\n".join(offenders)
    )


def _body_below_frontmatter(path: Path) -> str:
    """Markdown body with the leading YAML frontmatter block removed.

    The positive guard must verify the RC1 *body* reword, not the skill
    `description:` frontmatter: culture/SKILL.md's description legitimately says
    "BEFORE asking the user anything", which matches ASKING_PRIMARY regardless of
    the body sentence — so searching the whole file lets the guard pass vacuously
    even if the body regressed to a leaning phrasing. Scoping to the body forces
    the match to trace to the reword this guard exists to protect.
    """
    lines = path.read_text(encoding="utf-8").splitlines()
    if lines and lines[0].strip() == "---":
        for i in range(1, len(lines)):
            if lines[i].strip() == "---":
                return "\n".join(lines[i + 1 :])
    return "\n".join(lines)


def test_asking_primary_intent_present() -> None:
    # A pure negative guard passes vacuously if the dialogue framing is deleted
    # wholesale. Anchor the positive intent to the BODY (below the frontmatter):
    # each file must still make asking the user the explicit move in its prose, so
    # the reword's purpose can't be hollowed out. Matching the whole file would be
    # vacuous for culture — its `description:` frontmatter already says "asking
    # the user", independent of the body sentence RC1 reworded.
    missing = [
        str(p.relative_to(REPO_ROOT))
        for p in SCOPED_FILES
        if not ASKING_PRIMARY.search(_body_below_frontmatter(p))
    ]
    assert not missing, (
        "RC1 asking-primary intent ('ask the user …') absent from the body of: "
        + ", ".join(missing)
    )
