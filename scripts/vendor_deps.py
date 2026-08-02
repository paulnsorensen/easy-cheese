#!/usr/bin/env python3
"""Materialize vendor/ from requirements-vendor.txt.

The extracted wheel trees under vendor/ are what scripts/build_pyz.py stages
into ultracook.pyz and what the repo-root conftest binds the test suite to, but
they are generated, not committed: a hand-extracted tree is invisible to
Dependabot, while the hash-pinned requirements file next to it is watched.

Reproducibility comes from the pins, not from the bytes being on disk already —
a PyPI wheel filename maps to immutable bytes, and unpacking a zip copies member
bytes verbatim. The cost is that this step needs the network, so `just vendor`
runs once per lock change rather than on every build.

Idempotent: re-running with an unchanged lock and a populated tree does nothing.
"""

from __future__ import annotations

import argparse
import hashlib
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
LOCK = REPO_ROOT / "requirements-vendor.txt"
VENDOR_ROOT = REPO_ROOT / "vendor"
STAMP = VENDOR_ROOT / ".lock-stamp"


class VendorError(RuntimeError):
    """Raised when the vendored tree cannot be produced or trusted."""


def lock_digest() -> str:
    return hashlib.sha256(LOCK.read_bytes()).hexdigest()


def pinned_versions() -> dict[str, str]:
    """The lock's `name == version` pins, keyed by distribution name."""
    pins: dict[str, str] = {}
    for line in LOCK.read_text(encoding="utf-8").splitlines():
        if line.lstrip().startswith("#") or "==" not in line:
            continue
        name, rest = line.split("==", 1)
        pins[name.strip()] = rest.split()[0]
    return pins


def is_current() -> bool:
    """True when vendor/ was built from the lock file as it stands now."""
    if not STAMP.is_file():
        return False
    return STAMP.read_text(encoding="utf-8").strip() == lock_digest()


def require_populated(consumer: str) -> None:
    """Guard for consumers of vendor/ — build_pyz and the repo-root conftest.

    Raises rather than letting the caller fail later with a bare ImportError on
    `attrs`, which reads as a broken environment instead of a missing step.
    """
    if not is_current():
        raise VendorError(
            f"{consumer} needs the vendored dependencies in {VENDOR_ROOT}, which are "
            "generated and not committed. Run: just vendor"
        )


def _download(dest: Path) -> list[Path]:
    subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "download",
            "--no-deps",
            "--only-binary=:all:",
            "--require-hashes",
            "--requirement",
            str(LOCK),
            "--dest",
            str(dest),
        ],
        check=True,
    )
    wheels = sorted(dest.glob("*.whl"))
    if not wheels:
        raise VendorError(f"pip download produced no wheels in {dest}")
    return wheels


def vendor() -> None:
    if not LOCK.is_file():
        raise VendorError(f"missing lock file {LOCK}")

    with tempfile.TemporaryDirectory(prefix="ec-vendor-") as tmp:
        staging = Path(tmp) / "vendor"
        staging.mkdir()
        for wheel in _download(Path(tmp)):
            with zipfile.ZipFile(wheel) as zf:
                zf.extractall(staging)

        # Replace only after every wheel unpacked, so a mid-run failure leaves
        # the previous tree intact rather than a half-populated one.
        if VENDOR_ROOT.exists():
            shutil.rmtree(VENDOR_ROOT)
        shutil.move(str(staging), str(VENDOR_ROOT))

    STAMP.write_text(lock_digest() + "\n", encoding="utf-8")
    print(f"vendored {LOCK.name} into {VENDOR_ROOT}")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="exit non-zero if vendor/ is missing or stale, without downloading",
    )
    args = parser.parse_args(argv[1:])

    try:
        if args.check:
            require_populated("this repo")
            print(f"{VENDOR_ROOT} is current for {LOCK.name}")
        elif is_current():
            print(f"{VENDOR_ROOT} is already current for {LOCK.name}")
        else:
            vendor()
    except (VendorError, subprocess.CalledProcessError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
