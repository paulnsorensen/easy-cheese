"""The /age `review-evidence` command: static evidence for a review range.

The command compares the working tree with a base revision. It runs the
easy-cheese-review rule pack on the changed files and computes the `compat`,
`dependencies`, `tests`, and `scope` facts. Hits are evidence to confirm or
reject, never findings by themselves. Without ast-grep, the result has
`scan.status: failed:ast-grep-missing`, no hits, and every fact `unknown`,
and the review continues.
"""

from __future__ import annotations

import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path
from typing import cast

import fromargs

from easy_cheese.shared import git_utils
from easy_cheese_review import hunks_from_diff, scan

_GIT_TIMEOUT_SECONDS = 120
# Pin the diff path spelling: no C-style quotes and fixed a/ and b/ prefixes,
# whatever core.quotePath, diff.mnemonicPrefix, or diff.noprefix say.
_DIFF_OPTIONS = ["--no-renames", "--no-color", "--no-ext-diff", "--src-prefix=a/", "--dst-prefix=b/"]


def _git_text(repo: Path, args: list[str]) -> str:
    result = git_utils.run_git(
        ["-c", "core.quotePath=false", *args], cwd=repo, timeout=_GIT_TIMEOUT_SECONDS
    )
    if result.returncode != 0:
        raise fromargs.CliError(f"git {args[0]} failed: {result.stderr.strip()}")
    return result.stdout


def _extract_base(repo: Path, base: str, target: Path) -> None:
    """Stream `git archive <base>` into `target`, keeping regular files and folders.

    Links are skipped: the facts never follow a link, and an absolute or
    out-of-tree link would stop the extraction.
    """
    with subprocess.Popen(
        ["git", "-C", str(repo), "archive", "--format=tar", base],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=False,
    ) as process:
        assert process.stdout is not None and process.stderr is not None
        read_error: tarfile.ReadError | None = None
        try:
            with tarfile.open(fileobj=process.stdout, mode="r|") as archive:
                for member in archive:
                    if member.isfile() or member.isdir():
                        archive.extract(member, target, filter="data")
        except tarfile.ReadError as exc:
            # A failed `git archive` writes no tar; report git's own error first.
            read_error = exc
        stderr = cast(bytes, process.stderr.read()).decode("utf-8", errors="replace").strip()
        if process.wait(timeout=_GIT_TIMEOUT_SECONDS) != 0:
            raise fromargs.CliError(f"git archive {base} failed: {stderr}")
        if read_error is not None:
            raise fromargs.CliError(f"git archive {base} output is not a tar: {read_error}")


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
