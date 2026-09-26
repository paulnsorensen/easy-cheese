"""Register/repair the cheese-durable hallouminate corpus (ADR cheese-corpus-setup).

Writes the ~/.config/hallouminate/config.toml [[corpus]] block that points
hallouminate at the durable XDG corpus (paths.corpus_home()), fixes drift,
migrates the legacy skill-installed cheese-global -> ~/.cheese block, and
registers a repo as a hallouminate tenant via init-repo. Marked-block text
manipulation only -- no toml dependency.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import TypedDict

import fromargs

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


_migrate_legacy = migrate_legacy


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


def _changes_payload(changes: list[Change]) -> dict[str, object]:
    return {"changes": [_report(change) for change in changes]}


def global_cmd(*, apply: bool = False, migrate_legacy: bool = False) -> dict[str, object]:
    """Register or repair the durable Hallouminate corpus.

    Parameters
    ----------
    apply
        Write changes; default only reports.
    migrate_legacy
        Also remove a legacy cheese-global -> ~/.cheese block.
    """
    changes = [apply_global(apply=apply)]
    if migrate_legacy:
        changes.append(_migrate_legacy(apply=apply))
    return _changes_payload(changes)


def local_cmd(*, apply: bool = False) -> dict[str, object]:
    """Register or repair this repository's Hallouminate tenant.

    Parameters
    ----------
    apply
        Write changes; default only reports.
    """
    return _changes_payload([apply_local(Path.cwd(), apply=apply)])


def doctor_cmd(*, apply: bool = False) -> dict[str, object]:
    """Run the global, local, and artifacts registration legs.

    Parameters
    ----------
    apply
        Write changes; default only reports.
    """
    changes = [apply_global(apply=apply)]
    if not apply:
        changes.append(_migrate_legacy(apply=False))
    changes.append(apply_local(Path.cwd(), apply=apply))
    payload = _changes_payload(changes)
    payload["artifacts"] = list(hallouminate_artifacts.run_leg(apply=apply, roots=()))
    return payload


def artifacts_cmd(*, apply: bool = False, root: list[str] | None = None) -> dict[str, object]:
    """Register every .cheese directory as one Hallouminate corpus.

    Parameters
    ----------
    apply
        Write changes; default only reports.
    root
        Root directory to scan (repeatable); default: cwd only.
    """
    return {"artifacts": list(hallouminate_artifacts.run_leg(apply=apply, roots=root or []))}


def build_global_app() -> fromargs.App:
    return fromargs.App(
        "global",
        help="Register or repair the durable Hallouminate corpus.",
        help_formatter="plain",
        default_command=global_cmd,
    )


def global_main(argv: list[str] | None = None) -> int:  # noqa: V103
    return build_global_app().run(argv)


def build_local_app() -> fromargs.App:
    return fromargs.App(
        "local",
        help="Register or repair this repository's Hallouminate tenant.",
        help_formatter="plain",
        default_command=local_cmd,
    )


def local_main(argv: list[str] | None = None) -> int:  # noqa: V103
    return build_local_app().run(argv)


def build_doctor_app() -> fromargs.App:
    return fromargs.App(
        "doctor",
        help="Run the global, local, and artifacts registration legs.",
        help_formatter="plain",
        default_command=doctor_cmd,
    )


def doctor_main(argv: list[str] | None = None) -> int:  # noqa: V103
    return build_doctor_app().run(argv)


def build_artifacts_app() -> fromargs.App:
    return fromargs.App(
        "artifacts",
        help="Register every .cheese directory as one Hallouminate corpus.",
        help_formatter="plain",
        default_command=artifacts_cmd,
    )


def artifacts_main(argv: list[str] | None = None) -> int:  # noqa: V103
    return build_artifacts_app().run(argv)


LEAVES = ("global", "local", "doctor", "artifacts")


def build_app() -> fromargs.App:
    app = fromargs.App(
        "hallouminate-setup",
        help="Register or repair the Hallouminate corpus and repo tenant.",
        help_formatter="plain",
    )
    _ = app.command(global_cmd, name="global")
    _ = app.command(local_cmd, name="local")
    _ = app.command(doctor_cmd, name="doctor")
    _ = app.command(artifacts_cmd, name="artifacts")
    return app


def main(argv: list[str] | None = None) -> int:
    return build_app().run(argv)


if __name__ == "__main__":
    raise SystemExit(main())
