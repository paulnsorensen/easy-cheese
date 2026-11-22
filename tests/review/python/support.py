"""Helpers the easy-cheese-review suites share.

The suites import this module as `tests.review.python.support`, like
`tests/shared/python/bucket_cli.py`. A plain `from conftest import ...` would
resolve to the repository-root `conftest.py` in the `tests` environment.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from pathlib import Path

from easy_cheese_review import Fact, facts

WriteTree = Callable[[Path, Mapping[str, str]], Path]


def fake_ast_grep(tmp_path: Path, write_tree: WriteTree, script: str) -> str:
    """Write an executable `ast-grep` with the given script and return its path."""
    fake = write_tree(tmp_path / "bin", {"ast-grep": script}) / "ast-grep"
    fake.chmod(0o755)
    return str(fake)


def compute_facts(
    tmp_path: Path,
    write_tree: WriteTree,
    binary: str,
    *,
    base: Mapping[str, str],
    head: Mapping[str, str],
    changed: Sequence[str],
) -> dict[str, Fact]:
    """Write the `base` and `head` trees under `tmp_path` and compute the facts of the change."""
    base_root = tmp_path / "base"
    head_root = tmp_path / "head"
    base_root.mkdir(exist_ok=True)
    head_root.mkdir(exist_ok=True)
    _ = write_tree(base_root, base)
    _ = write_tree(head_root, head)
    return facts(head_root, changed, base=base_root, ast_grep=binary)
