"""The /age `review-evidence` command: static evidence for a review range.

The command compares the working tree with a base revision. It runs the
easy-cheese-review rule pack on the changed files and computes the `compat`,
`dependencies`, `tests`, and `scope` facts. Hits are evidence to confirm or
reject, never findings by themselves. Without ast-grep, the result has
`scan.status: failed:ast-grep-missing`, no hits, and `unknown` `compat`,
`dependencies`, and `scope` facts with a reason. The `tests` fact needs no
ast-grep, so it is still computed. The review continues. A file above the
package size limit is not scanned; `scan.skipped` names it.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
import threading
from pathlib import Path, PurePosixPath
from typing import IO, cast

import fromargs

from easy_cheese_review import SCAN_SUFFIXES, hunks_from_diff, scan

_GIT_TIMEOUT_SECONDS = 120
_DRAIN_BYTES = 64 * 1024
# Pin the diff path spelling: fixed a/ and b/ prefixes, whatever
# diff.mnemonicPrefix or diff.noprefix say. `core.quotePath=false` stops the
# quoting of non-ASCII bytes only. Git still puts C-style quotes on a name that
# holds `"`, `\`, or a control character, and `hunks_from_diff` undoes them.
# `--text` prints a hunk for every file, so no `-diff` attribute or NUL byte
# in the reviewed tree hides a changed line. `--no-textconv` keeps the hunk
# line numbers on the lines of the file on disk, whatever textconv driver the
# `.gitattributes` of the reviewed tree selects.
_DIFF_OPTIONS = [
    "--text",
    "--no-textconv",
    "--no-renames",
    "--no-color",
    "--no-ext-diff",
    "--src-prefix=a/",
    "--dst-prefix=b/",
]
# Regular files only: links (120000) and submodules (160000) are skipped.
_REGULAR_FILE_MODES = frozenset({"100644", "100755"})


def _git_text(repo: Path, args: list[str]) -> str:
    """Return the output of a git command as text that keeps every byte.

    The bytes decode as UTF-8 with `surrogateescape` and no newline
    translation. A file name that is not UTF-8 thus goes back to the file
    system unchanged, and a lone carriage return stays in its line.
    """
    result = subprocess.run(
        ["git", "-C", str(repo), "-c", "core.quotePath=false", *args],
        capture_output=True,
        timeout=_GIT_TIMEOUT_SECONDS,
        check=False,
    )
    if result.returncode != 0:
        stderr = result.stderr.decode("utf-8", errors="replace").strip()
        raise fromargs.CliError(f"git {args[0]} failed: {stderr}")
    return result.stdout.decode("utf-8", errors="surrogateescape")


def _base_code_blobs(repo: Path, base: str) -> list[tuple[str, str]]:
    """Return `(path, object id)` for each regular code file in the `base` tree."""
    listing = _git_text(repo, ["ls-tree", "-r", "-z", "--full-tree", base])
    blobs: list[tuple[str, str]] = []
    for entry in listing.split("\0"):
        meta, _, path = entry.partition("\t")
        fields = meta.split()
        if len(fields) != 3 or fields[0] not in _REGULAR_FILE_MODES or fields[1] != "blob":
            continue
        # The base import scan reads the whole base tree; `dependencies` needs
        # the imports of every file that ast-grep parses there.
        if PurePosixPath(path).suffix in SCAN_SUFFIXES:
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


def _write_next_blob(stream: IO[bytes], object_id: str, destination: Path | None) -> bool:
    """Move the next `cat-file --batch` answer to `destination`.

    Return False when the answer is not the whole blob `object_id`. A None
    `destination` reads the blob and writes nothing.
    """
    header = stream.readline().split()
    if len(header) != 3 or header[0] != object_id.encode("ascii") or header[1] != b"blob":
        return False
    size = int(header[2])
    # Git writes one line feed after each blob.
    data = stream.read(size + 1)
    if len(data) != size + 1:
        return False
    if destination is not None:
        destination.parent.mkdir(parents=True, exist_ok=True)
        _ = destination.write_bytes(memoryview(data)[:size])
    return True


def _extract_base(repo: Path, base: str, target: Path) -> None:
    """Write the regular code files of `base` into `target` from raw git blobs.

    `git cat-file --batch` applies no attribute, so `export-ignore`,
    `export-subst`, filters, and line-ending conversion change nothing.
    The facts read only code files and never follow a link, so links,
    submodules, and other files are skipped.

    One `cat-file` process serves the whole tree and each blob goes to its
    file before the next blob is read. The request comes from a temporary
    file, not a pipe, so git never waits on a full output pipe while this
    process still writes the request.
    """
    blobs = _base_code_blobs(repo, base)
    if not blobs:
        return
    command = ["git", "-C", str(repo), "cat-file", "--batch"]
    timed_out = threading.Event()
    lost: str | None = None
    with tempfile.TemporaryFile() as request, tempfile.TemporaryFile() as errors:
        _ = request.write("".join(f"{object_id}\n" for _, object_id in blobs).encode("ascii"))
        _ = request.seek(0)
        with subprocess.Popen(command, stdin=request, stdout=subprocess.PIPE, stderr=errors) as proc:

            def expire() -> None:
                timed_out.set()
                proc.kill()

            timer = threading.Timer(_GIT_TIMEOUT_SECONDS, expire)
            timer.start()
            stream = cast(IO[bytes], proc.stdout)
            try:
                for path, object_id in blobs:
                    if not _write_next_blob(stream, object_id, _inside(target, path)):
                        lost = path
                        break
                # After a bad answer, read to the end so git exits with its own status.
                while stream.read(_DRAIN_BYTES):
                    pass
                returncode = proc.wait()
            finally:
                proc.kill()
                timer.cancel()
        _ = errors.seek(0)
        stderr = errors.read().decode("utf-8", errors="replace").strip()
    if timed_out.is_set():
        raise subprocess.TimeoutExpired(command, _GIT_TIMEOUT_SECONDS)
    if returncode != 0:
        raise fromargs.CliError(f"git cat-file {base} failed: {stderr}")
    if lost is not None:
        raise fromargs.CliError(f"git cat-file {base}: no blob for {lost}")


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
