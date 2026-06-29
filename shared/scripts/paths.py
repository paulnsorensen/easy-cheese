"""Slug validation and corpus path math.

Used by every workflow skill that writes a corpus artifact. Durable phases
(``specs``, ``research``) anchor at a stable per-project XDG location; transient
pipeline phases stay repo-local under ``.cheese/``. See ``default_root_for_phase``.

The canonical slug pattern matches cheese-factory's manifest-schema.json so a
slug accepted by one validator is accepted by all.
"""

from __future__ import annotations

import difflib
import functools
import os
import re
import subprocess
from pathlib import Path

# Source of truth: skills/cheese-factory/references/manifest-schema.json.
# Kebab-case, no leading/trailing hyphen, no double hyphens, 1-64 chars.
# If manifest-schema.json changes (e.g., adding allowed characters), this regex
# must be updated in lockstep — keep in sync via manual review.
KEBAB_SLUG = re.compile(r"^(?!-)(?!.*--)[a-z0-9-]{1,64}(?<!-)$")

# Phases that own a `.cheese/<phase>/<slug>.md` artifact tree. The set spans
# phases owned by several orchestrators (`/cheese-factory`, `/pasteurize`,
# `/research`) plus one-off notes/specs/hard artifacts.
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

# Phases whose artifacts are durable, project-scoped knowledge worth a stable
# home outside any single checkout: a spec or research report stays useful
# across branches and clones and shouldn't ride along in git. They anchor at the
# per-project XDG corpus. Every other phase is transient pipeline handoff state
# (cook/press/age/cure reports, notes, hard explanations) and stays repo-local
# under .cheese/ where it travels with the branch and surfaces in the PR.
XDG_PHASES: frozenset[str] = frozenset({"specs", "research"})

# Repo-local root for transient phases. Relative on purpose: it resolves against
# the working directory so artifacts live with the branch being worked on.
REPO_LOCAL_ROOT = Path(".cheese")

# Phases of the cook → press → age → cure pipeline chain.
CHAIN_PHASES: tuple[str, ...] = ("cook", "press", "age", "cure")

# Phase token -> on-disk directory name, when the two diverge. The phase TOKEN
# stays stable for every caller (artifact_path, parse, resolver); only the
# directory under the root differs. `hard` writes to `.cheese/hard-cheese/`,
# matching src/hard-cheese/append-attempt.py. Phases not listed map to
# themselves.
PHASE_DIRS: dict[str, str] = {"hard": "hard-cheese"}
_DIR_PHASES: dict[str, str] = {d: p for p, d in PHASE_DIRS.items()}

# Aux registry: artifact owners that are NOT pipeline phases. `affinage` writes
# `.cheese/affinage/pr-<n>.md` keyed by PR number (not a kebab slug) and has no
# chain semantics, so it stays out of PHASES but the resolver still finds it.
AUX_PHASES: frozenset[str] = frozenset({"affinage"})

# Phase/aux token -> slash-command skill that owns it. Mostly identity
# (`/<phase>`); these are the exceptions.
PHASE_SKILL: dict[str, str] = {
    "hard": "/hard-cheese",
    "specs": "/mold",
    "notes": "/wheypoint",
    "research": "/briesearch",
    "affinage": "/affinage",
}


def phase_dir(phase: str) -> str:
    """On-disk directory name for a phase token (identity unless in PHASE_DIRS)."""
    return PHASE_DIRS.get(phase, phase)


def phase_skill(phase: str) -> str:
    """Slash-command skill that owns a phase/aux token (identity `/<phase>` default)."""
    return PHASE_SKILL.get(phase, f"/{phase}")


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


_STOPWORDS = frozenset(
    {"a", "an", "and", "the", "of", "for", "to", "in", "on", "with", "is"}
)


def slugify(text: str, *, max_words: int = 5) -> str:
    """Best-effort kebab-slug from arbitrary text."""
    lowered = re.sub(r"[^a-z0-9\s-]+", "", text.lower())
    words = [w for w in lowered.split() if w and w not in _STOPWORDS]
    slug = "-".join(words[:max_words])
    slug = re.sub(r"-+", "-", slug).strip("-")
    return slug[:64]


def _xdg_dir(env_var: str, *default: str) -> Path:
    """An XDG base dir from ``env_var``, or ``~/<default...>`` as the fallback.

    Per the XDG Base Directory spec, a value that is not an absolute path is
    ignored in favour of the default.
    """
    raw = os.environ.get(env_var, "").strip()
    if raw and os.path.isabs(raw):
        return Path(raw)
    return Path.home().joinpath(*default)


def xdg_data_home() -> Path:
    """``$XDG_DATA_HOME`` or ``~/.local/share``."""
    return _xdg_dir("XDG_DATA_HOME", ".local", "share")


def _sanitize_segment(name: str) -> str:
    """Collapse arbitrary text into one filesystem-safe path segment.

    No separators and no traversal survive, so the result is always a single
    directory name. Empty input falls back to ``default``.
    """
    cleaned = re.sub(r"[^a-z0-9._-]+", "-", name.strip().lower())
    cleaned = re.sub(r"-{2,}", "-", cleaned).strip("-._")
    return (cleaned or "default")[:96]


def _slug_from_remote(url: str) -> str:
    """Reduce a git remote URL to its trailing ``owner/repo``.

    Handles scp-style (``git@host:owner/repo.git``) and URL-style
    (``https://host/owner/repo``) remotes; the ``.git`` suffix is dropped. The
    last two path segments are kept, so credential/host prefixes, proxy path
    prefixes, and GitLab subgroups all collapse to a stable ``owner/repo``.
    """
    s = url.strip()
    if s.endswith(".git"):
        s = s[:-4]
    if "//" in s:  # scheme://host/owner/repo
        s = re.sub(r"^[a-z][a-z0-9+.-]*://[^/]+/", "", s)
    elif ":" in s:  # scp-like git@host:owner/repo
        s = s.split(":", 1)[1]
    segments = [seg for seg in s.strip("/").split("/") if seg]
    return "/".join(segments[-2:])


@functools.lru_cache(maxsize=1)
def _git_identity() -> str | None:
    """``owner/repo`` from origin, else the git toplevel dir name, else None."""
    try:
        remote = subprocess.run(
            ["git", "config", "--get", "remote.origin.url"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if remote.returncode == 0 and remote.stdout.strip():
            return _slug_from_remote(remote.stdout.strip())
        top = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if top.returncode == 0 and top.stdout.strip():
            return Path(top.stdout.strip()).name
    except (OSError, subprocess.SubprocessError):
        return None
    return None


def project_key() -> str:
    """Stable per-project corpus key, matching the git repository.

    ``$EASY_CHEESE_PROJECT`` wins when set; otherwise the origin ``owner/repo``
    (e.g. ``paulnsorensen-easy-cheese``), the git toplevel name, or finally the
    working-directory name. Always a single sanitized path segment.
    """
    override = os.environ.get("EASY_CHEESE_PROJECT", "").strip()
    if override:
        return _sanitize_segment(override)
    identity = _git_identity()
    if identity:
        return _sanitize_segment(identity.replace("/", "-"))
    return _sanitize_segment(Path.cwd().name)


def corpus_home() -> Path:
    """Base dir holding every project's durable corpus.

    ``$EASY_CHEESE_HOME`` overrides when it is an absolute path (a relative value
    is ignored, matching the XDG convention); otherwise ``$XDG_DATA_HOME/cheese``
    (default ``~/.local/share/cheese``).
    """
    override = os.environ.get("EASY_CHEESE_HOME", "").strip()
    if override and os.path.isabs(override):
        return Path(override)
    return xdg_data_home() / "cheese"


def project_corpus_root(project: str | None = None) -> Path:
    """``<corpus_home>/<project>`` — the per-project durable corpus root."""
    return corpus_home() / (project or project_key())


def default_root_for_phase(phase: str, *, project: str | None = None) -> Path:
    """Where a phase's artifacts live when no explicit ``root`` is given.

    Durable phases (see ``XDG_PHASES``) anchor at the per-project XDG corpus;
    everything else stays repo-local under ``.cheese/``.
    """
    if phase in XDG_PHASES:
        return project_corpus_root(project)
    return REPO_LOCAL_ROOT


def artifact_path(phase: str, slug: str, *, root: Path | str | None = None) -> Path:
    """Return ``<root>/<phase>/<slug>.md``. Validates phase + slug.

    With ``root`` omitted, the root is resolved per phase via
    ``default_root_for_phase`` (durable phases → XDG corpus, rest → ``.cheese/``).
    Pass ``root=`` to override, e.g. a pytest ``tmp_path``.

    Covers flat-phase artifacts (specs, transient reports). Research long-form
    reports use a nested ``research/<slug>/<slug>.md`` layout composed from
    ``project_corpus_root()`` by ``/briesearch``; this flat helper is not that path.
    """
    if phase not in PHASES:
        raise ValueError(f"unknown phase {phase!r}; expected one of {sorted(PHASES)}")
    err = validate_slug(slug)
    if err is not None:
        raise ValueError(err)
    base = Path(root) if root is not None else default_root_for_phase(phase)
    return base / phase_dir(phase) / f"{slug}.md"


def parse_artifact_path(path: Path | str) -> tuple[str, str]:
    """Parse ``phase, slug`` from a canonical ``.cheese/<phase>/<slug>.md`` path.

    Only the canonical ``.cheese/`` root is parsed.
    """
    p = Path(path)
    parts = p.parts
    if len(parts) < 3 or parts[-3] != ".cheese":
        raise ValueError(f"{path!r} is not under .cheese/<phase>/")
    dir_name = parts[-2]
    phase = _DIR_PHASES.get(dir_name, dir_name)
    if phase not in PHASES:
        raise ValueError(f"unknown phase {dir_name!r} in {path!r}")
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
    """Return ``{phase: path}`` for each chain-phase artifact present on disk."""
    err = validate_slug(slug)
    if err is not None:
        raise ValueError(err)
    found: dict[str, Path] = {}
    for phase in phases:
        candidate = Path(root) / phase_dir(phase) / f"{slug}.md"
        if candidate.is_file():
            found[phase] = candidate
    return found


def _git_toplevel() -> Path | None:
    """Absolute git worktree root, or None outside a repo."""
    try:
        top = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if top.returncode == 0 and top.stdout.strip():
        return Path(top.stdout.strip())
    return None


def _resolve_repo_root(repo_root: Path | str | None) -> Path:
    """Absolute repo root: the given value, else git toplevel, else cwd."""
    if repo_root is not None:
        return Path(repo_root).resolve()
    return (_git_toplevel() or Path.cwd()).resolve()


def _phase_dirpath(phase: str, repo_root: Path) -> Path:
    """Absolute artifact directory for a phase/aux token."""
    base = project_corpus_root() if phase in XDG_PHASES else repo_root / ".cheese"
    return base / phase_dir(phase)


def _phase_entries(phase: str, repo_root: Path) -> list[tuple[str, Path]]:
    """``(stem, abs_path)`` for every artifact present in a phase's directory.

    The stem is the slug-shaped key used for exact and fuzzy matching. Honors
    the irregular layouts: ``research/<slug>/<slug>.md`` (nested),
    ``cheese-factory/<slug>/manifest.yaml`` (dir + manifest), and the flat
    ``<dir>/<slug>.md`` everywhere else.
    """
    dirpath = _phase_dirpath(phase, repo_root)
    if not dirpath.is_dir():
        return []
    entries: list[tuple[str, Path]] = []
    if phase == "research":
        for sub in dirpath.iterdir():
            nested = sub / f"{sub.name}.md"
            if sub.is_dir() and nested.is_file():
                entries.append((sub.name, nested))
        entries.extend((f.stem, f) for f in dirpath.glob("*.md"))
    elif phase == "cheese-factory":
        for sub in dirpath.iterdir():
            manifest = sub / "manifest.yaml"
            if sub.is_dir() and manifest.is_file():
                entries.append((sub.name, manifest))
        entries.extend((f.stem, f) for f in dirpath.glob("*.md"))
    else:
        entries.extend((f.stem, f) for f in dirpath.glob("*.md"))
    return entries


# Below this ratio a fuzzy stem match is noise, not a near-miss.
_FUZZY_CUTOFF = 0.6


def resolve_slug(
    slug: str,
    *,
    phase_hint: str | None = None,
    repo_root: Path | str | None = None,
) -> dict:
    """Resolve a slug to absolute artifact path(s) without relative-path guessing.

    Three tiers: exact stem match (confidence 1.0), fuzzy stem match
    (confidence = difflib ratio), then a fallback listing the absolute phase-dir
    roots searched so the caller can grep them directly.

    ``phase_hint``, when it names a known phase/aux token, restricts the search
    to that one directory; otherwise every known token is searched.
    """
    err = validate_slug(slug)
    if err is not None:
        raise ValueError(err)
    known = sorted(PHASES | AUX_PHASES)
    if phase_hint is not None and phase_hint not in known:
        raise ValueError(f"unknown phase {phase_hint!r}; expected one of {known}")
    repo = _resolve_repo_root(repo_root)
    phases = [phase_hint] if phase_hint is not None else known

    exact: list[dict] = []
    fuzzy_pool: list[tuple[str, Path, str]] = []
    searched_roots: list[str] = []
    for phase in phases:
        searched_roots.append(str(_phase_dirpath(phase, repo)))
        for stem, path in _phase_entries(phase, repo):
            if stem == slug:
                exact.append(
                    {
                        "abs_path": str(path),
                        "phase": phase,
                        "skill": phase_skill(phase),
                        "confidence": 1.0,
                    }
                )
            else:
                fuzzy_pool.append((stem, path, phase))

    if exact:
        exact.sort(key=lambda m: (m["phase"], m["abs_path"]))
        return {"matches": exact, "fallback_roots": []}

    fuzzy: list[dict] = []
    for stem, path, phase in fuzzy_pool:
        ratio = difflib.SequenceMatcher(None, slug, stem).ratio()
        if ratio >= _FUZZY_CUTOFF:
            fuzzy.append(
                {
                    "abs_path": str(path),
                    "phase": phase,
                    "skill": phase_skill(phase),
                    "confidence": round(ratio, 3),
                }
            )
    if fuzzy:
        fuzzy.sort(key=lambda m: (-m["confidence"], m["phase"], m["abs_path"]))
        return {"matches": fuzzy, "fallback_roots": []}

    return {"matches": [], "fallback_roots": sorted(set(searched_roots))}
