"""Unit tests for scripts/check_bundles.py classification."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts"))
import check_bundles  # noqa: E402


def test_classify_git_show_missing_path_is_new_bundle() -> None:
    assert (
        check_bundles.classify_git_show(
            128, b"fatal: path 'skills/cut/scripts/cut.pyz' does not exist in 'HEAD'\n"
        )
        == "missing"
    )
    assert (
        check_bundles.classify_git_show(
            128,
            b"fatal: path 'x.pyz' exists on disk, but not in 'HEAD'\n",
        )
        == "missing"
    )


def test_classify_git_show_other_failures_are_errors() -> None:
    assert check_bundles.classify_git_show(128, b"fatal: not a git repository\n") == "error"
    assert check_bundles.classify_git_show(128, b"fatal: Invalid object name 'HEAD'.\n") == "error"
    assert check_bundles.classify_git_show(0, b"") == "ok"
