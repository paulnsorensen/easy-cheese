#!/usr/bin/env python3
"""Check every committed .pyz still matches its sources, by content.

Run after `build_pyz.py` has rebuilt the working tree: this compares each
rebuilt bundle against the copy committed at HEAD.

The comparison uses per-member content signatures rather than raw archive bytes.
Shiv assembles deterministic wheel members, but ZIP metadata and interpreter
paths can vary between toolchains. Host-specific fields are canonicalized; a
source edit that never made it into the committed bundle still fails this gate.

Every .pyz must carry Shiv's runtime markers; other zipapp formats are rejected.
"""

from __future__ import annotations

import io
import hashlib
import json
import re
import subprocess
import sys
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
BUNDLE_GLOB = "skills/*/scripts/*.pyz"

SHIV_RUNTIME_MEMBERS = frozenset(
    {
        "_bootstrap/__init__.py",
        "_bootstrap/environment.py",
        "_bootstrap/filelock.py",
        "_bootstrap/interpreter.py",
        "__main__.py",
        "environment.json",
    }
)


def _validate_shiv_archive(archive: zipfile.ZipFile) -> None:
    names = set(archive.namelist())
    missing = sorted(SHIV_RUNTIME_MEMBERS - names)
    if missing:
        raise ValueError(f"not a Shiv archive: missing {', '.join(missing)}")
    if not any(name.startswith("site-packages/") for name in names):
        raise ValueError("not a Shiv archive: missing site-packages/")


def _site_packages_hash(
    archive: zipfile.ZipFile,
    *,
    normalize_wrappers: bool,
    include_record: bool,
) -> str:
    digest = hashlib.sha256()
    members = sorted(
        [
            info
            for info in archive.infolist()
            if info.filename.startswith("site-packages/")
            and not info.filename.endswith("/")
            and not info.filename.endswith(".pyc")
            and (include_record or not info.filename.endswith(".dist-info/RECORD"))
        ],
        key=lambda info: info.filename,
    )
    for info in members:
        data = archive.read(info)
        if normalize_wrappers and info.filename.startswith("site-packages/bin/"):
            data = _canonical_wrapper(data)
        relative = info.filename.removeprefix("site-packages/")
        digest.update(data)
        digest.update(relative.encode())
    return digest.hexdigest()


def _canonical_environment(data: bytes, *, canonical_build_id: str) -> bytes:
    """Normalize Shiv's host timestamp and derive a portable cache ID."""
    environment = json.loads(data)
    environment.pop("built_at", None)
    environment["build_id"] = canonical_build_id
    return json.dumps(environment, sort_keys=True, separators=(",", ":")).encode()


def _canonical_wrapper(data: bytes) -> bytes:
    """Normalize only the interpreter token, retaining shebang arguments."""
    def replace(match: re.Match[bytes]) -> bytes:
        line = match.group(0)
        command_line = line[2:]
        if command_line.startswith(b"/usr/bin/env "):
            command_line = command_line[len(b"/usr/bin/env ") :]
        token, separator, args = command_line.partition(b" ")
        executable = token.rsplit(b"/", 1)[-1]
        if not re.fullmatch(rb"python(?:\d+(?:\.\d+)*)?", executable):
            return line
        suffix = separator + args
        return b"#!<python>" + suffix

    return re.sub(rb"(?m)^#![^\n]*", replace, data, count=1)


def _manifest(data: bytes) -> dict[str, tuple[int, int] | bytes]:
    """Source member name -> (CRC, uncompressed size).

    Shiv generates RECORD files and host-specific interpreter paths from the
    local toolchain. Execution configuration and wrapper bodies remain signals;
    only those host-dependent fields are canonicalized.
    """
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        _validate_shiv_archive(archive)
        environment = json.loads(archive.read("environment.json"))
        stored_build_id = environment.get("build_id")
        raw_build_id = _site_packages_hash(
            archive, normalize_wrappers=False, include_record=True
        )
        if stored_build_id != raw_build_id:
            raise ValueError(
                "Shiv build_id does not match site-packages contents: "
                f"stored {stored_build_id!r}, expected {raw_build_id}"
            )
        canonical_build_id = _site_packages_hash(
            archive, normalize_wrappers=True, include_record=False
        )
        manifest: dict[str, tuple[int, int] | bytes] = {}
        for info in archive.infolist():
            if info.filename.endswith(".dist-info/RECORD"):
                continue
            if info.filename == "environment.json":
                manifest[info.filename] = _canonical_environment(
                    archive.read(info), canonical_build_id=canonical_build_id
                )
            elif info.filename.startswith("site-packages/bin/"):
                manifest[info.filename] = _canonical_wrapper(archive.read(info))
            else:
                manifest[info.filename] = (info.CRC, info.file_size)
        return manifest


def _committed(path: Path) -> bytes | None:
    """The blob at HEAD, or None when the bundle is newly added."""
    result = subprocess.run(
        ["git", "show", f"HEAD:{path.as_posix()}"],
        cwd=REPO_ROOT,
        capture_output=True,
    )
    return result.stdout if result.returncode == 0 else None


def _describe(
    rebuilt: dict[str, tuple[int, int] | bytes],
    committed: dict[str, tuple[int, int] | bytes],
) -> list[str]:
    problems = []
    for name in sorted(set(rebuilt) - set(committed)):
        problems.append(f"    + {name} (built, not in the committed bundle)")
    for name in sorted(set(committed) - set(rebuilt)):
        problems.append(f"    - {name} (committed, no longer built)")
    for name in sorted(set(rebuilt) & set(committed)):
        if rebuilt[name] != committed[name]:
            problems.append(f"    ~ {name} (content differs)")
    return problems


def main() -> int:
    stale: list[str] = []
    for path in sorted(REPO_ROOT.glob("skills/*/scripts/common.pyz")):
        stale.append(f"  {path.relative_to(REPO_ROOT)} (obsolete shared bundle)")
    checked = 0
    for path in sorted(REPO_ROOT.glob(BUNDLE_GLOB)):
        relative = path.relative_to(REPO_ROOT)
        committed = _committed(relative)
        checked += 1
        try:
            rebuilt_manifest = _manifest(path.read_bytes())
            if committed is None:
                print(f"new Shiv bundle, nothing to compare: {relative}")
                continue
            committed_manifest = _manifest(committed)
            problems = _describe(rebuilt_manifest, committed_manifest)
        except (ValueError, KeyError, json.JSONDecodeError, zipfile.BadZipFile) as exc:
            problems = [f"    ! bundle metadata invalid: {exc}"]
        if problems:
            stale.append(f"  {relative}\n" + "\n".join(problems))

    if stale:
        print(
            "::error::.pyz bundles are invalid or stale; run "
            "'python3 scripts/build_pyz.py' and commit the generated "
            "skills/*/scripts/*.pyz files."
        )
        print("\n".join(stale))
        return 1

    print(f".pyz bundles are current ({checked} checked, by canonical member content).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
