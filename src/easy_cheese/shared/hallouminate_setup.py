"""Register/repair the cheese-durable hallouminate corpus (ADR cheese-corpus-setup).

Writes the ~/.config/hallouminate/config.toml [[corpus]] block that points
hallouminate at the durable XDG corpus (paths.corpus_home()), fixes drift,
migrates the legacy skill-installed cheese-global -> ~/.cheese block, and
registers a repo as a hallouminate tenant via init-repo. Marked-block text
manipulation only -- no toml dependency.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import TypedDict, cast

from easy_cheese.shared import paths
from easy_cheese.shared import hallouminate_artifacts
from easy_cheese.shared.hallouminate_blocks import (
    Change as Change,
    atomic_write,
    config_path as config_path,
    extract_block,
    find_marked_span,
    replace_marked_block,
    resolve_config_path,
)


class _State(TypedDict):
    present: bool
    path: str | None
    drifted: bool
    drift_from: str | None


BEGIN = "# >>> easy-cheese:cheese-durable"
END = "# <<< easy-cheese:cheese-durable"

_PATHS0_RE = re.compile(r'paths\s*=\s*\[\s*"([^"]*)"')


def _block(home: Path) -> str:
    return (
        f"{BEGIN}\n"
        "[[corpus]]\n"
        'name = "cheese-durable"\n'
        f'paths = ["{home}"]\n'
        'globs = ["**/*.md"]\n'
        'exclude = ["**/.git/**"]\n'
        f"{END}\n"
    )


def detect_state(config_path: Path | None = None) -> _State:
    """``{present, path, drifted, drift_from}`` for the marked cheese-durable block.

    ``drifted`` is True when the block is present but its ``paths[0]`` does not
    match ``paths.corpus_home()``.
    """
    path = resolve_config_path(config_path)
    if not path.is_file():
        return {"present": False, "path": None, "drifted": False, "drift_from": None}
    block = extract_block(path.read_text(encoding="utf-8"), begin=BEGIN, end=END)
    if block is None:
        return {
            "present": False,
            "path": str(path),
            "drifted": False,
            "drift_from": None,
        }
    match = _PATHS0_RE.search(block)
    current = match.group(1) if match else None
    home = str(paths.corpus_home())
    # current is None for a malformed/truncated block with no parseable paths
    # line -- treat that as drift so apply_global rewrites it cleanly.
    drifted = current != home
    return {
        "present": True,
        "path": str(path),
        "drifted": drifted,
        "drift_from": current if drifted else None,
    }


def apply_global(config_path: Path | None = None, *, apply: bool) -> Change:
    """Insert-or-replace the marked cheese-durable [[corpus]] block.

    Also ``mkdir -p`` ``corpus_home()`` (hallouminate aborts if the corpus dir
    is missing -- issue #101) whenever ``apply=True``, regardless of whether
    the block itself needs a write. Replace-in-place, never blind-append --
    hallouminate errors on duplicate corpus names. Idempotent: a second
    ``apply=True`` run leaves the file byte-identical.
    """
    path = resolve_config_path(config_path)
    home = paths.corpus_home()
    state = detect_state(path)
    if not state["present"]:
        action, detail = "create", f"register cheese-durable at {home}"
    elif state["drifted"]:
        from_desc = state["drift_from"] or "a malformed block"
        action, detail = "replace", f"repoint cheese-durable from {from_desc} to {home}"
    else:
        action, detail = "noop", f"cheese-durable already points at {home}"

    if not apply:
        return Change("global", action, str(path), detail)

    home.mkdir(parents=True, exist_ok=True)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        _ = path.write_text("", encoding="utf-8")
    if action != "noop":
        # read_bytes (not read_text) so CRLF endings survive verbatim on
        # every Python -- read_text(newline=...) is 3.13+, CI runs 3.12.
        text = path.read_bytes().decode("utf-8")
        atomic_write(
            path, replace_marked_block(text, _block(home), begin=BEGIN, end=END)
        )
    return Change("global", action, str(path), detail)


def _unmarked_corpus_sections(text: str) -> list[tuple[int, int]]:
    """``(start_idx, end_idx_exclusive)`` line ranges of ``[[corpus]]`` sections
    that fall outside the marked cheese-durable block."""
    lines = text.splitlines(keepends=True)
    marked_span = find_marked_span(lines, begin=BEGIN, end=END)
    sections: list[tuple[int, int]] = []
    i = 0
    n = len(lines)
    while i < n:
        if marked_span is not None and marked_span[0] <= i <= marked_span[1]:
            i = marked_span[1] + 1
            continue
        if lines[i].strip() == "[[corpus]]":
            start = i
            i += 1
            # End the section at the next TOML table header ([table] or
            # [[array]]) or the marked block -- NOT at EOF. Running to EOF would
            # let migrate_legacy delete a trailing [[repository]]/[settings]
            # section that follows the last [[corpus]] block.
            while i < n:
                stripped = lines[i].strip()
                if (
                    stripped.startswith("[")
                    or stripped.startswith("# >>> easy-cheese:")
                    or stripped.startswith("# <<< easy-cheese:")
                ):
                    break
                i += 1
            sections.append((start, i))
            continue
        i += 1
    return sections


def migrate_legacy(config_path: Path | None = None, *, apply: bool) -> Change:
    """Remove an UNMARKED ``cheese-global`` [[corpus]] block pointing at
    ``~/.cheese`` (the legacy skill-installed drift). A ``cheese-global``
    block pointing anywhere else is left untouched. Skill-only leg -- never
    called from install.sh, so the installer stays non-destructive.
    """
    path = resolve_config_path(config_path)
    no_legacy = Change(
        "global", "noop", str(path), "no legacy cheese-global block found"
    )
    if not path.is_file():
        return no_legacy
    # read_bytes (not read_text) so CRLF endings survive verbatim on
    # every Python -- read_text(newline=...) is 3.13+, CI runs 3.12.
    text = path.read_bytes().decode("utf-8")
    lines = text.splitlines(keepends=True)
    for start, end in _unmarked_corpus_sections(text):
        section = "".join(lines[start:end])
        if 'name = "cheese-global"' in section and '"~/.cheese"' in section:
            detail = "remove legacy cheese-global -> ~/.cheese block"
            if not apply:
                return Change("global", "remove", str(path), detail)
            updated = "".join(lines[:start]) + "".join(lines[end:])
            atomic_write(path, updated)
            return Change("global", "remove", str(path), detail)
    return no_legacy


def _git(repo_root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo_root), *args],
        capture_output=True,
        text=True,
        check=True,
    ).stdout


def _main_root(repo_root: Path) -> Path:
    """The MAIN worktree root, never a Conductor-style linked worktree."""
    porcelain = _git(repo_root, "worktree", "list", "--porcelain")
    for line in porcelain.splitlines():
        if line.startswith("worktree "):
            return Path(line[len("worktree ") :])
    common_dir = _git(
        repo_root, "rev-parse", "--path-format=absolute", "--git-common-dir"
    ).strip()
    return Path(common_dir).parent


def _run_init_repo(name: str, path: Path) -> None:
    _ = subprocess.run(
        ["hallouminate", "init-repo", name, "--path", str(path)], check=True
    )


def apply_local(repo_root: Path, *, apply: bool) -> Change:
    """Register the repo as a hallouminate tenant, iff ``.cheese/`` exists and
    the MAIN repo root (not a Conductor-style worktree) isn't already one.
    """
    repo_root = Path(repo_root)
    if not (repo_root / ".cheese").is_dir():
        return Change(
            "local", "noop", str(repo_root), "no .cheese/ directory; not a cheese repo"
        )
    try:
        main_root = _main_root(repo_root)
    except subprocess.CalledProcessError:
        return Change(
            "local",
            "noop",
            str(repo_root),
            ".cheese/ present but not a git repo; skipping init-repo",
        )
    if (main_root / ".hallouminate" / "config.toml").is_file():
        return Change("local", "noop", str(main_root), "already a hallouminate tenant")
    name = main_root.name
    detail = f"hallouminate init-repo {name} --path {main_root}"
    if not apply:
        return Change("local", "init-repo", str(main_root), detail)
    _run_init_repo(name, main_root)
    return Change("local", "init-repo", str(main_root), detail)


def _report(change: Change) -> str:
    return f"[{change.leg}] {change.action}: {change.target_path} -- {change.detail}"


def _run_leg(
    leg: str, do_apply: bool, migrate: bool = False, roots: Sequence[str] = ()
) -> int:
    if leg in ("global", "doctor"):
        print(_report(apply_global(apply=do_apply)))
        if migrate:
            print(_report(migrate_legacy(apply=do_apply)))
    if leg == "doctor" and not do_apply and not migrate:
        print(_report(migrate_legacy(apply=False)))
    if leg in ("local", "doctor"):
        print(_report(apply_local(Path.cwd(), apply=do_apply)))
    if leg in ("artifacts", "doctor"):
        for line in hallouminate_artifacts.run_leg(apply=do_apply, roots=roots):
            print(line)
    return 0


def _leg_main(leg: str, argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog=leg)
    _ = parser.add_argument("--apply", action="store_true")
    _ = parser.add_argument("--migrate-legacy", action="store_true")
    _ = parser.add_argument("--root", action="append", default=[])
    args = parser.parse_args(argv)
    do_apply = cast(bool, args.apply)
    migrate = cast(bool, args.migrate_legacy)
    roots = cast("list[str]", args.root)
    if migrate and leg != "global":
        parser.error("--migrate-legacy is only valid for global")
    if roots and leg != "artifacts":
        parser.error("--root is only valid for artifacts")
    return _run_leg(leg, do_apply, migrate, roots)


def global_main(argv: list[str]) -> int:  # noqa: V103
    return _leg_main("global", argv)


def local_main(argv: list[str]) -> int:  # noqa: V103
    return _leg_main("local", argv)


def doctor_main(argv: list[str]) -> int:  # noqa: V103
    return _leg_main("doctor", argv)


def artifacts_main(argv: list[str]) -> int:  # noqa: V103
    return _leg_main("artifacts", argv)


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv if argv is None else argv
    legs = {"global", "local", "doctor", "artifacts"}
    prog0 = Path(argv[0]).name
    if prog0 in legs:
        leg, rest = prog0, argv[1:]
    elif len(argv) >= 2 and argv[1] in legs:
        leg, rest = argv[1], argv[2:]
    else:
        _ = sys.stderr.write(
            "usage: hallouminate_setup.py {global|local|doctor|artifacts} [--apply]\n"
        )
        return 2
    return _leg_main(leg, rest)


if __name__ == "__main__":
    sys.exit(main())
