"""Register/repair the cheese-durable hallouminate corpus (ADR cheese-corpus-setup).

Writes the ~/.config/hallouminate/config.toml [[corpus]] block that points
hallouminate at the durable XDG corpus (paths.corpus_home()), fixes drift,
migrates the legacy skill-installed cheese-global -> ~/.cheese block, and
registers a repo as a hallouminate tenant via init-repo. Marked-block text
manipulation only -- no toml dependency.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import paths

BEGIN = "# >>> easy-cheese:cheese-durable"
END = "# <<< easy-cheese:cheese-durable"

_PATHS0_RE = re.compile(r'paths\s*=\s*\[\s*"([^"]*)"')


@dataclass(frozen=True)
class Change:
    """One leg's computed or applied action, for reporting + idempotency checks."""

    leg: str
    action: str  # "noop" | "create" | "replace" | "remove" | "init-repo"
    target_path: str
    detail: str


def config_path() -> Path:
    """``${XDG_CONFIG_HOME:-~/.config}/hallouminate/config.toml``.

    ``$HALLOUMINATE_CONFIG`` overrides outright (tests point this at a temp file).
    """
    override = os.environ.get("HALLOUMINATE_CONFIG", "").strip()
    if override:
        return Path(override)
    raw = os.environ.get("XDG_CONFIG_HOME", "").strip()
    base = Path(raw) if raw and os.path.isabs(raw) else Path.home() / ".config"
    return base / "hallouminate" / "config.toml"


def _resolve_config_path(explicit: Path | None) -> Path:
    return Path(explicit) if explicit is not None else config_path()


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


def _find_marked_span(lines: list[str]) -> tuple[int, int] | None:
    """``(begin_idx, end_idx)`` (inclusive) of the marked block, or None.

    An orphan ``BEGIN`` with no closing ``END`` (a half-written/truncated block)
    spans begin→EOF, so it is replaced in place rather than left to trip the
    blind-append path into a duplicate cheese-durable corpus.
    """
    begin_idx = None
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped == BEGIN:
            begin_idx = i
        elif stripped == END and begin_idx is not None:
            return begin_idx, i
    if begin_idx is not None:
        return begin_idx, len(lines) - 1
    return None


def _atomic_write(path: Path, text: str) -> None:
    """Write via a temp sibling + ``os.replace`` so an interrupted write can
    never truncate the shared user config (it holds unrelated corpora)."""
    tmp = path.with_name(f"{path.name}.ec-tmp")
    # write_bytes (not write_text) so line endings pass through verbatim on
    # every Python -- write_text(newline=...) is 3.13+, CI runs 3.12.
    tmp.write_bytes(text.encode("utf-8"))
    os.replace(tmp, path)


def _extract_block(text: str) -> str | None:
    lines = text.splitlines(keepends=True)
    span = _find_marked_span(lines)
    if span is None:
        return None
    begin_idx, end_idx = span
    return "".join(lines[begin_idx : end_idx + 1])


def _dominant_newline(text: str) -> str:
    """The config's prevailing line ending, so a rewritten block does not mix
    CRLF and LF in a shared user config that is CRLF-terminated."""
    crlf = text.count("\r\n")
    lf_only = text.count("\n") - crlf
    return "\r\n" if crlf > lf_only else "\n"


def _replace_marked_block(text: str, new_block: str) -> str:
    newline = _dominant_newline(text)
    if newline != "\n":
        new_block = new_block.replace("\r\n", "\n").replace("\n", newline)
    lines = text.splitlines(keepends=True)
    span = _find_marked_span(lines)
    if span is not None:
        begin_idx, end_idx = span
        return "".join(lines[:begin_idx]) + new_block + "".join(lines[end_idx + 1 :])
    prefix = text
    if prefix and not prefix.endswith(("\n", "\r\n")):
        prefix += newline
    return prefix + new_block


def detect_state(config_path: Path | None = None) -> dict:
    """``{present, path, drifted, drift_from}`` for the marked cheese-durable block.

    ``drifted`` is True when the block is present but its ``paths[0]`` does not
    match ``paths.corpus_home()``.
    """
    path = _resolve_config_path(config_path)
    if not path.is_file():
        return {"present": False, "path": None, "drifted": False, "drift_from": None}
    block = _extract_block(path.read_text(encoding="utf-8"))
    if block is None:
        return {"present": False, "path": str(path), "drifted": False, "drift_from": None}
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
    path = _resolve_config_path(config_path)
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
        path.write_text("", encoding="utf-8")
    if action != "noop":
        # read_bytes (not read_text) so CRLF endings survive verbatim on
        # every Python -- read_text(newline=...) is 3.13+, CI runs 3.12.
        text = path.read_bytes().decode("utf-8")
        _atomic_write(path, _replace_marked_block(text, _block(home)))
    return Change("global", action, str(path), detail)


def _unmarked_corpus_sections(text: str) -> list[tuple[int, int]]:
    """``(start_idx, end_idx_exclusive)`` line ranges of ``[[corpus]]`` sections
    that fall outside the marked cheese-durable block."""
    lines = text.splitlines(keepends=True)
    marked_span = _find_marked_span(lines)
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
                if stripped.startswith("[") or stripped in (BEGIN, END):
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
    path = _resolve_config_path(config_path)
    no_legacy = Change("global", "noop", str(path), "no legacy cheese-global block found")
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
            _atomic_write(path, updated)
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
    common_dir = _git(repo_root, "rev-parse", "--path-format=absolute", "--git-common-dir").strip()
    return Path(common_dir).parent


def _run_init_repo(name: str, path: Path) -> None:
    subprocess.run(["hallouminate", "init-repo", name, "--path", str(path)], check=True)


def apply_local(repo_root: Path, *, apply: bool) -> Change:
    """Register the repo as a hallouminate tenant, iff ``.cheese/`` exists and
    the MAIN repo root (not a Conductor-style worktree) isn't already one.
    """
    repo_root = Path(repo_root)
    if not (repo_root / ".cheese").is_dir():
        return Change("local", "noop", str(repo_root), "no .cheese/ directory; not a cheese repo")
    try:
        main_root = _main_root(repo_root)
    except subprocess.CalledProcessError:
        return Change("local", "noop", str(repo_root), ".cheese/ present but not a git repo; skipping init-repo")
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


def _run_leg(leg: str, do_apply: bool) -> int:
    if leg in ("global", "doctor"):
        print(_report(apply_global(apply=do_apply)))
    if leg == "doctor" and not do_apply:
        print(_report(migrate_legacy(apply=False)))
    if leg in ("local", "doctor"):
        print(_report(apply_local(Path.cwd(), apply=do_apply)))
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv if argv is None else argv
    legs = {"global", "local", "doctor"}
    prog0 = Path(argv[0]).name
    if prog0 in legs:
        leg, rest = prog0, argv[1:]
    elif len(argv) >= 2 and argv[1] in legs:
        leg, rest = argv[1], argv[2:]
    else:
        sys.stderr.write("usage: hallouminate_setup.py {global|local|doctor} [--apply]\n")
        return 2
    parser = argparse.ArgumentParser(prog=leg)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args(rest)
    return _run_leg(leg, args.apply)


if __name__ == "__main__":
    sys.exit(main())
