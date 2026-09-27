"""Multi-component /cook candidate: reach allowlist, token-budget guard, build gate.

A candidate is a dict mapping repo-relative paths to their full text. Reach is
limited to `skills/cook/SKILL.md`, `skills/cook/references/*.md`, and
`src/easy_cheese/skills/cook/**/*.py`. When a CODE_PREFIX component's text
differs from HEAD, the build step runs inside a disposable
`git worktree add --detach HEAD` copy of the repository; otherwise it reads
only HEAD's `skills/cook` tree through `git archive`. Neither path ever
writes into the caller's checkout.
"""

from __future__ import annotations

import contextlib
import io
import json
import shutil
import subprocess
import sys
import tarfile
import tempfile
from collections.abc import Callable, Generator, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import cast


Candidate = dict[str, str]
CommandRunner = Callable[[Sequence[str], Path], "subprocess.CompletedProcess[str]"]

# token_budget_guard delegates the actual token count and budget check to
# .github/scripts/validate_skills.py (imported lazily below); that script is
# the source of truth for TARGET_TOKENS and the budget file.
SKILL_MD_PATH = "skills/cook/SKILL.md"
REFERENCES_PREFIX = "skills/cook/references/"
CODE_PREFIX = "src/easy_cheese/skills/cook/"
BUILD_GUARD = "build"
TOKEN_BUDGET_GUARD = "token-budget"
MAX_TAIL = 4_000
PLUGIN_NAME = "easy-cheese"
SKILL_DIR_NAME = "cook"


class CandidateError(ValueError):
    """A candidate component path is outside the allowed reach."""


@dataclass(frozen=True)
class BuildResult:
    """Outcome of `build_candidate`: a guard name, or None on success."""

    guard: str | None
    detail: str = ""


def path_escapes(rel_path: str) -> bool:
    """Return True when `rel_path` is absolute or contains a `..` segment.

    Shared by `validate_candidate` here and by `agent_lab_scoring`'s
    component-path check, so the two modules do not carry drifting copies
    of the same escape predicate.
    """
    path = PurePosixPath(rel_path)
    return path.is_absolute() or ".." in path.parts


def _is_allowed(rel_path: str) -> bool:
    if path_escapes(rel_path):
        return False
    text = PurePosixPath(rel_path).as_posix()
    if text == SKILL_MD_PATH:
        return True
    if text.startswith(REFERENCES_PREFIX) and text.endswith(".md"):
        return True
    if text.startswith(CODE_PREFIX) and text.endswith(".py"):
        return True
    return False


def validate_candidate(candidate: Candidate) -> None:
    """Raise CandidateError when any component path escapes the allowed reach."""
    for rel_path in candidate:
        if not _is_allowed(rel_path):
            raise CandidateError(f"candidate component path is out of reach: {rel_path}")


def load_candidate_dir(base_dir: Path) -> Candidate:
    """Read every allowed component found under `base_dir` at its own relative path.

    `base_dir` mirrors the repo root's layout (it can be the repo root
    itself), so the same function loads the current checkout's candidate or a
    standalone candidate directory.
    """
    candidate: Candidate = {}
    resolved_base = base_dir.resolve()
    for pattern in (SKILL_MD_PATH, f"{REFERENCES_PREFIX}*.md", f"{CODE_PREFIX}**/*.py"):
        for path in sorted(base_dir.glob(pattern)):
            if not path.is_file():
                continue
            if path.is_symlink():
                continue
            resolved_path = path.resolve()
            if resolved_base not in resolved_path.parents and resolved_path != resolved_base:
                continue
            rel_path = path.relative_to(base_dir).as_posix()
            candidate[rel_path] = path.read_text(encoding="utf-8")
    return candidate


def token_budget_guard(candidate: Candidate) -> str | None:
    """Return TOKEN_BUDGET_GUARD when the candidate's SKILL.md is over budget."""
    text = candidate.get(SKILL_MD_PATH)
    if text is None:
        return None
    script_dir = Path(__file__).resolve().parents[1] / ".github" / "scripts"
    script_dir_str = str(script_dir)
    inserted = script_dir_str not in sys.path
    if inserted:
        sys.path.insert(0, script_dir_str)
    try:
        import validate_skills  # pyright: ignore[reportMissingImports]
    finally:
        if inserted:
            sys.path.remove(script_dir_str)
    tokens = cast(int, validate_skills.body_tokens(text))  # pyright: ignore[reportUnknownMemberType]
    budgets = cast("dict[str, object]", validate_skills.load_budgets())  # pyright: ignore[reportUnknownMemberType]
    errors = cast("list[str]", validate_skills.validate_size(Path(SKILL_MD_PATH), tokens, budgets))  # pyright: ignore[reportUnknownMemberType]
    return TOKEN_BUDGET_GUARD if errors else None


def _head_text(repo_root: Path, rel_path: str) -> str | None:
    """Return the text of `rel_path` at HEAD, or None when it does not exist there."""
    completed = subprocess.run(
        ["git", "show", f"HEAD:{rel_path}"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )
    return completed.stdout if completed.returncode == 0 else None


def has_code_changes(repo_root: Path, candidate: Candidate) -> bool:
    """Return True when a CODE_PREFIX component's text differs from HEAD.

    A candidate seeded from the current checkout (or a GEPA mutation that
    only touches SKILL.md or a reference) carries CODE_PREFIX components
    whose text is byte-identical to HEAD; those never need a rebuild.
    """
    return any(
        _head_text(repo_root, rel_path) != text
        for rel_path, text in candidate.items()
        if rel_path.startswith(CODE_PREFIX)
    )


def _default_run(argv: Sequence[str], cwd: Path) -> "subprocess.CompletedProcess[str]":
    return subprocess.run(list(argv), cwd=cwd, capture_output=True, text=True, check=False)


def _base_command(worktree: Path) -> list[str]:
    """The interpreter argv prefix for a build step run inside `worktree`.

    Reuses the worktree's own pinned lockfiles through `uv run` when present,
    same as `scripts/check_bundles.py`'s isolated rebuild; falls back to the
    running interpreter otherwise (the default fake-run test seam never
    reaches this fallback for real work).
    """
    runtime_requirements = worktree / "requirements" / "runtime.txt"
    build_requirements = worktree / "requirements-build.txt"
    if runtime_requirements.is_file() and build_requirements.is_file():
        return [
            "uv",
            "run",
            "--no-project",
            "--with-requirements",
            str(runtime_requirements),
            "--with-requirements",
            str(build_requirements),
            "--with",
            "pytest==9.0.3",
            "--with",
            "pyyaml==6.0.2",
            "python3",
        ]
    return [sys.executable]


@contextlib.contextmanager
def _detached_worktree(repo_root: Path) -> Generator[Path]:
    """Check out HEAD into a disposable worktree; remove it on exit.

    The candidate build only ever mutates this copy, never `repo_root`.
    """
    with tempfile.TemporaryDirectory(prefix="agent-lab-candidate-") as scratch:
        worktree = Path(scratch) / "worktree"
        _ = subprocess.run(
            ["git", "worktree", "add", "--detach", "--quiet", str(worktree), "HEAD"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=True,
        )
        try:
            yield worktree
        finally:
            removed = subprocess.run(
                ["git", "worktree", "remove", "--force", str(worktree)],
                cwd=repo_root,
                capture_output=True,
                text=True,
                check=False,
            )
            if removed.returncode != 0:
                message = f"warning: git worktree remove failed for {worktree}: {removed.stderr.strip()}; running git worktree prune"
                print(message, file=sys.stderr)
                _ = subprocess.run(
                    ["git", "worktree", "prune"],
                    cwd=repo_root,
                    capture_output=True,
                    text=True,
                    check=False,
                )


@contextlib.contextmanager
def _tracked_skills_cook(repo_root: Path) -> Generator[Path]:
    """Extract `skills/cook` at HEAD into a disposable dir mirroring the repo.

    Used when no rebuild is needed: it reads only HEAD's `skills/cook` tree
    through `git archive`, so the build never pays for a full-repository
    worktree checkout and never sees `repo_root`'s working-tree state.
    """
    with tempfile.TemporaryDirectory(prefix="agent-lab-candidate-") as scratch:
        root = Path(scratch) / "snapshot"
        root.mkdir()
        archive = subprocess.run(
            ["git", "archive", "HEAD", "skills/cook"],
            cwd=repo_root,
            capture_output=True,
            check=True,
        )
        with tarfile.open(fileobj=io.BytesIO(archive.stdout)) as tar:
            tar.extractall(root)
        yield root


def write_components(base_dir: Path, candidate: Mapping[str, str]) -> None:
    """Write every component's text to its own path under `base_dir`.

    Public so `agent_lab_scoring` can share this writer instead of keeping
    its own copy.
    """
    for rel_path, text in candidate.items():
        dest = base_dir / rel_path
        dest.parent.mkdir(parents=True, exist_ok=True)
        _ = dest.write_text(text, encoding="utf-8")


def build_candidate(
    candidate: Candidate,
    *,
    repo_root: Path,
    overlay_dir: Path,
    run: CommandRunner | None = None,
) -> BuildResult:
    """Assemble `overlay_dir` as a `.claude-plugin` overlay for `candidate`.

    When a CODE_PREFIX component's text differs from HEAD, this regenerates
    the runtime, the `references/commands.md` projection, and `cook.pyz`,
    then runs cook's own tests -- all inside a disposable worktree. A
    failure at any of those steps returns BUILD_GUARD and leaves
    `overlay_dir` untouched: every step that can fail runs before
    `overlay_dir` is ever written. Otherwise the tracked
    `skills/cook/scripts/cook.pyz` is reused as-is, read straight from HEAD
    without checking out the rest of the repository.
    """
    validate_candidate(candidate)
    runner = run or _default_run
    code_changed = has_code_changes(repo_root, candidate)
    context = _detached_worktree(repo_root) if code_changed else _tracked_skills_cook(repo_root)
    with context as root:
        write_components(root, candidate)
        if code_changed:
            base = _base_command(root)
            steps = [
                [*base, "scripts/build_pyz.py", "--write-generated"],
                [*base, "scripts/render_generated_regions.py"],
            ]
            test_files = sorted(
                str(path.relative_to(root))
                for path in root.glob("tests/python/test_cook_*.py")
            )
            if test_files:
                steps.append([*base, "-m", "pytest", *test_files, "-q"])
            steps.append(
                [*base, "scripts/build_pyz.py", "cook", "--out-dir", str(root / "skills" / "cook" / "scripts")]
            )
            for step in steps:
                completed = runner(step, root)
                if completed.returncode != 0:
                    tail = (completed.stdout + completed.stderr)[-MAX_TAIL:]
                    return BuildResult(BUILD_GUARD, tail)
        skills_cook = overlay_dir / "skills" / "cook"
        skills_cook.parent.mkdir(parents=True, exist_ok=True)
        if skills_cook.exists():
            shutil.rmtree(skills_cook)
        _ = shutil.copytree(root / "skills" / "cook", skills_cook)
    plugin_dir = overlay_dir / ".claude-plugin"
    plugin_dir.mkdir(parents=True, exist_ok=True)
    plugin = {"name": PLUGIN_NAME, "skills": [f"./skills/{SKILL_DIR_NAME}"]}
    _ = (plugin_dir / "plugin.json").write_text(json.dumps(plugin) + "\n", encoding="utf-8")
    return BuildResult(None)


def prepare_overlay_detailed(
    candidate: Candidate,
    *,
    repo_root: Path,
    overlay_dir: Path,
    run: CommandRunner | None = None,
) -> BuildResult:
    """Run the token-budget guard then the build gate; return the full
    `BuildResult` (guard name and detail), unlike `prepare_overlay`, which
    discards `detail`. Used where a guard's detail must reach CLI output.

    Both guards make zero runner calls: the caller must check `.guard`
    before ever invoking a benchmark run for `candidate`.

    `build_candidate` is the single validation entry point (it always
    calls `validate_candidate` first), so this does not validate again.
    """
    guard = token_budget_guard(candidate)
    if guard:
        return BuildResult(guard)
    return build_candidate(candidate, repo_root=repo_root, overlay_dir=overlay_dir, run=run)


def prepare_overlay(
    candidate: Candidate,
    *,
    repo_root: Path,
    overlay_dir: Path,
    run: CommandRunner | None = None,
) -> str | None:
    """Run the token-budget guard then the build gate; return a guard name or None.

    Both guards make zero runner calls: the caller must check this return
    value before ever invoking a benchmark run for `candidate`.
    """
    return prepare_overlay_detailed(candidate, repo_root=repo_root, overlay_dir=overlay_dir, run=run).guard
