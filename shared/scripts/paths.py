"""Slug validation and ``.cheese/<phase>/<slug>.md`` path math.

Used by every workflow skill that writes a `.cheese/` artifact. The canonical
slug pattern matches cheese-factory's manifest-schema.json so a slug accepted
by one validator is accepted by all.
"""

from __future__ import annotations

import re
from pathlib import Path

# Source of truth: skills/cheese-factory/references/manifest-schema.json.
# Kebab-case, no leading/trailing hyphen, no double hyphens, 1-64 chars.
# If manifest-schema.json changes (e.g., adding allowed characters), this regex
# must be updated in lockstep — keep in sync via manual review.
KEBAB_SLUG = re.compile(r"^(?!-)(?!.*--)[a-z0-9-]{1,64}(?<!-)$")

# Phases that own a `.cheese/<phase>/<slug>.md` artifact tree. Different
# orchestrators scan different subsets — see CHAIN_PHASES below for the
# pipeline that `/cheese --continue` walks. The wider set here includes
# phases owned by other orchestrators (`/cheese-factory`, `/pasteurize`,
# `/research`) and one-off notes/specs/hard artifacts.
PHASES: frozenset[str] = frozenset(
    {
        "cook",
        "press",
        "age",
        "cure",
        "specs",
        "notes",
        "hard",
        "research",
        "cheese-factory",
        "pasteurize",
    }
)

CHAIN_PHASES: tuple[str, ...] = ("cook", "press", "age", "cure")


def is_valid_slug(slug: str) -> bool:
    return bool(KEBAB_SLUG.match(slug))


def validate_slug(slug: str) -> str | None:
    """Return an error string if invalid, else None."""
    if not isinstance(slug, str) or not slug:
        return "slug must be a non-empty string"
    if not KEBAB_SLUG.match(slug):
        return (
            f"slug {slug!r} must be kebab-case, 1-64 chars, [a-z0-9-], "
            "no leading/trailing hyphen, no double hyphens"
        )
    return None


# Stopwords dropped during slugify — too generic to carry meaning in a slug.
_STOPWORDS = frozenset(
    {"a", "an", "and", "the", "of", "for", "to", "in", "on", "with", "is"}
)


def slugify(text: str, *, max_words: int = 5) -> str:
    """Best-effort kebab-slug from arbitrary text. May still need validation."""
    # Drop punctuation, keep alphanumerics, whitespace, and hyphens. Apostrophes
    # are removed so "Don't" -> "dont", not "don-t".
    lowered = re.sub(r"[^a-z0-9\s-]+", "", text.lower())
    words = [w for w in lowered.split() if w and w not in _STOPWORDS]
    slug = "-".join(words[:max_words])
    slug = re.sub(r"-+", "-", slug).strip("-")
    return slug[:64]


def artifact_path(phase: str, slug: str, *, root: Path | str = ".cheese") -> Path:
    """Return ``<root>/<phase>/<slug>.md``. Validates phase + slug."""
    if phase not in PHASES:
        raise ValueError(f"unknown phase {phase!r}; expected one of {sorted(PHASES)}")
    err = validate_slug(slug)
    if err is not None:
        raise ValueError(err)
    return Path(root) / phase / f"{slug}.md"


def parse_artifact_path(path: Path | str) -> tuple[str, str]:
    """Extract (phase, slug) from a canonical ``.cheese/<phase>/<slug>.md`` path.

    Only the canonical root is parsed — paths produced by ``artifact_path``
    with a custom ``root=`` argument (e.g. a pytest ``tmp_path``) are not
    round-trippable here. Callers operating outside ``.cheese/`` should
    construct (phase, slug) themselves.
    """
    p = Path(path)
    parts = p.parts
    if len(parts) < 3 or parts[-3] != ".cheese":
        raise ValueError(f"{path!r} is not under .cheese/<phase>/")
    phase = parts[-2]
    if phase not in PHASES:
        raise ValueError(f"unknown phase {phase!r} in {path!r}")
    if p.suffix != ".md":
        raise ValueError(f"artifact must end in .md, got {p.suffix!r}")
    slug = p.stem
    err = validate_slug(slug)
    if err is not None:
        raise ValueError(err)
    return phase, slug


def existing_artifacts(
    slug: str, *, root: Path | str = ".cheese", phases: tuple[str, ...] = CHAIN_PHASES
) -> dict[str, Path]:
    """Return {phase: path} for each chain-phase artifact present on disk."""
    err = validate_slug(slug)
    if err is not None:
        raise ValueError(err)
    found: dict[str, Path] = {}
    for phase in phases:
        candidate = Path(root) / phase / f"{slug}.md"
        if candidate.is_file():
            found[phase] = candidate
    return found
