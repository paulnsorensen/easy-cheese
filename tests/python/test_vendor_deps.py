"""Tests for scripts/vendor_deps.py — the generated vendor/ tree's currency check.

vendor/ is untracked, so `is_current` is the only thing standing between a
half-populated tree and a bundle built without attrs in it.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
import vendor_deps

LOCK = """\
# comment line with an == that must not parse as a pin
attrs==26.1.0 --hash=sha256:aaaa
cattrs==26.1.0 --hash=sha256:bbbb
"""


@pytest.fixture
def fake_vendor(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A vendor root and lock file wired into the module, populated and current."""
    lock = tmp_path / "requirements-vendor.txt"
    lock.write_text(LOCK, encoding="utf-8")
    root = tmp_path / "vendor"
    root.mkdir()
    monkeypatch.setattr(vendor_deps, "LOCK", lock)
    monkeypatch.setattr(vendor_deps, "VENDOR_ROOT", root)
    monkeypatch.setattr(vendor_deps, "STAMP", root / ".lock-stamp")

    for name in ("attrs", "cattrs"):
        (root / f"{name}-26.1.0.dist-info").mkdir()
    vendor_deps.STAMP.write_text(
        hashlib.sha256(LOCK.encode()).hexdigest() + "\n", encoding="utf-8"
    )
    return root


def test_pinned_versions_reads_pins_not_comments(fake_vendor: Path) -> None:
    # The header comment carries an "==" of its own, and every pin is followed
    # by a --hash flag that must not end up in the version.
    assert vendor_deps.pinned_versions() == {"attrs": "26.1.0", "cattrs": "26.1.0"}


def test_current_tree_is_current(fake_vendor: Path) -> None:
    assert vendor_deps.is_current()


def test_stamp_without_the_trees_is_not_current(fake_vendor: Path) -> None:
    # The branch-switch case: .lock-stamp is gitignored, so checking out a
    # revision that predates this layout deletes the trees and leaves the stamp
    # behind, vouching for a directory that no longer has attrs in it.
    for child in (fake_vendor / "attrs-26.1.0.dist-info",):
        child.rmdir()
    assert not vendor_deps.is_current()


def test_lock_change_is_not_current(fake_vendor: Path) -> None:
    vendor_deps.LOCK.write_text(LOCK.replace("26.1.0", "26.2.0"), encoding="utf-8")
    assert not vendor_deps.is_current()


def test_require_populated_names_the_missing_step(fake_vendor: Path) -> None:
    vendor_deps.STAMP.unlink()
    with pytest.raises(vendor_deps.VendorError, match="just vendor"):
        vendor_deps.require_populated("the test suite")
