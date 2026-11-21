"""The /age `review-evidence` command: static evidence for a review range.

The command compares the working tree with a base revision. It runs the
easy-cheese-review rule pack on the changed files and computes the `compat`,
`dependencies`, `tests`, and `scope` facts. Hits are evidence to confirm or
reject, never findings by themselves. Without ast-grep, the result has
`scan.status: failed:ast-grep-missing`, no hits, and `unknown` `compat`,
`dependencies`, and `scope` facts with a reason. The `tests` fact needs no
ast-grep, so it is still computed. The review continues.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path, PurePosixPath

import fromargs

from easy_cheese.shared import git_utils
from easy_cheese_review import CODE_SUFFIXES, hunks_from_diff, scan

_GIT_TIMEOUT_SECONDS = 120
# Pin the diff path spelling: no C-style quotes and fixed a/ and b/ prefixes,
# whatever core.quotePath, diff.mnemonicPrefix, or diff.noprefix say.
# `--text` prints a hunk for every file, so no `-diff` attribute or NUL byte
# in the reviewed tree hides a changed line.
_DIFF_OPTIONS = [
    "--text",
    "--no-renames",
    "--no-color",
    "--no-ext-diff",
    "--src-prefix=a/",
    "--dst-prefix=b/",
]
# Regular files only: links (120000) and submodules (160000) are skipped.
_REGULAR_FILE_MODES = frozenset({"100644", "100755"})
# The base import scan reads the whole base tree, so ast-grep also parses these
# suffixes (measured with ast-grep 0.51.3); `dependencies` needs their imports.
_BASE_SCAN_SUFFIXES = CODE_SUFFIXES | frozenset({".mts", ".cts", ".pyi", ".py3", ".bzl"})


def _git_text(repo: Path, args: list[str]) -> str:
    result = git_utils.run_git(
        ["-c", "core.quotePath=false", *args], cwd=repo, timeout=_GIT_TIMEOUT_SECONDS
    )
    if result.returncode != 0:
        raise fromargs.CliError(f"git {args[0]} failed: {result.stderr.strip()}")
    return result.stdout


def _base_code_blobs(repo: Path, base: str) -> list[tuple[str, str]]:
    """Return `(path, object id)` for each regular code file in the `base` tree."""
    listing = _git_text(repo, ["ls-tree", "-r", "-z", "--full-tree", base])
    blobs: list[tuple[str, str]] = []
    for entry in listing.split("\0"):
        meta, _, path = entry.partition("\t")
        fields = meta.split()
        if len(fields) != 3 or fields[0] not in _REGULAR_FILE_MODES or fields[1] != "blob":
            continue
        if PurePosixPath(path).suffix in _BASE_SCAN_SUFFIXES:
            blobs.append((path, fields[2]))
    return blobs


def _inside(target: Path, path: str) -> Path | None:
    """Return where `path` goes under `target`, or None when it would leave `target`."""
    pure = PurePosixPath(path)
    if not pure.parts or pure.is_absolute() or ".." in pure.parts:
        return None
    destination = target.joinpath(*pure.parts)
    if not destination.resolve().is_relative_to(target.resolve()):
        return None
    return destination


def _extract_base(repo: Path, base: str, target: Path) -> None:
    """Write the regular code files of `base` into `target` from raw git blobs.

    `git cat-file --batch` applies no attribute, so `export-ignore`,
    `export-subst`, filters, and line-ending conversion change nothing.
    The facts read only code files and never follow a link, so links,
    submodules, and other files are skipped.
    """
    blobs = _base_code_blobs(repo, base)
    if not blobs:
        return
    request = "".join(f"{object_id}\n" for _, object_id in blobs).encode("ascii")
    result = subprocess.run(
        ["git", "-C", str(repo), "cat-file", "--batch"],
        input=request,
        capture_output=True,
        timeout=_GIT_TIMEOUT_SECONDS,
        check=False,
    )
    if result.returncode != 0:
        stderr = result.stderr.decode("utf-8", errors="replace").strip()
        raise fromargs.CliError(f"git cat-file {base} failed: {stderr}")
    output = result.stdout
    position = 0
    for path, object_id in blobs:
        header_end = output.find(b"\n", position)
        header = output[position:header_end].split()
        if header_end < 0 or len(header) != 3 or header[0] != object_id.encode("ascii") or header[1] != b"blob":
            raise fromargs.CliError(f"git cat-file {base}: no blob for {path}")
        start = header_end + 1
        end = start + int(header[2])
        position = end + 1
        destination = _inside(target, path)
        if destination is None:
            continue
        destination.parent.mkdir(parents=True, exist_ok=True)
        _ = destination.write_bytes(output[start:end])


def evidence_cmd(base: str, *, repo: str = ".") -> dict[str, object]:
    """Scan the changes from a base revision to the working tree for review evidence.

    Untracked files that git does not ignore count as changed in full.

    Parameters
    ----------
    base
        Base revision of the review range, for example a merge base or origin/main.
    repo
        Path to the git repository.
    """
    if base.startswith("-"):
        raise fromargs.CliError(f"base revision must not start with '-': {base!r}")
    root = Path(_git_text(Path(repo), ["rev-parse", "--show-toplevel"]).strip())
    names = _git_text(root, ["diff", "--name-only", "-z", "--no-renames", base, "--"])
    untracked = _git_text(root, ["ls-files", "--others", "--exclude-standard", "-z"])
    new_files = [name for name in untracked.split("\0") if name]
    changed = [name for name in names.split("\0") if name] + new_files
    hunks = hunks_from_diff(_git_text(root, ["diff", "--unified=0", *_DIFF_OPTIONS, base, "--"]))
    hunks.update({name: [(1, sys.maxsize)] for name in new_files})
    with tempfile.TemporaryDirectory(prefix="age-review-base-") as tmp:
        base_tree = Path(tmp)
        _extract_base(root, base, base_tree)
        evidence = scan(root, changed, base=base_tree, hunks=hunks)
    return evidence.to_json()


def build_app() -> fromargs.App:
    return fromargs.App(
        "review-evidence",
        help="Scan a review range with the easy-cheese-review rule pack and facts (JSON out).",
        help_formatter="plain",
        default_command=evidence_cmd,
    )


def main(argv: list[str] | None = None) -> int:
    return build_app().run(argv)


if __name__ == "__main__":
    raise SystemExit(main())
