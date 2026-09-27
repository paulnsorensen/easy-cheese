#!/usr/bin/env python3
"""Locate or build the skill archives that tests execute.

A test runs a skill through its built archive, not through the committed
launcher: the launcher trusts only the digest in the committed lock, and a
test must exercise the working tree's source. `EASY_CHEESE_PREBUILT_PYZ`
names a directory of `<skill>.pyz` files that `just test` and CI build once
with `--out-dir`; without it, the first request for a skill builds that
skill's archive into a per-process temporary directory through the pinned
wedge (scripts/wedge.py).

    python3 scripts/skill_archives.py --out-dir DIR [SKILL ...]
"""

from __future__ import annotations

import argparse
import atexit
import json
import os
import shutil
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import cast

sys.path.insert(0, str(Path(__file__).resolve().parent))
import runtime_gates  # noqa: E402  (sibling module in scripts/)
import wedge  # noqa: E402  (sibling module in scripts/)

REPO_ROOT = runtime_gates.REPO_ROOT
SKILLS = runtime_gates.SKILLS
PREBUILT_ENV = "EASY_CHEESE_PREBUILT_PYZ"

_process_dir: Path | None = None
_built: dict[str, Path] = {}


def prebuilt_dir() -> Path | None:
    """The prebuilt archive directory, or None when the variable is unset.

    A present but unusable value is a configuration error, not a reason to
    rebuild silently: a typo would otherwise cost every caller a full build
    while the run still reported success.
    """
    value = os.environ.get(PREBUILT_ENV)
    if not value:
        return None
    candidate = Path(value)
    hint = "rebuild the set, or unset the variable to build archives on demand"
    if not candidate.is_dir():
        raise ValueError(f"{PREBUILT_ENV}={value!r} is not a directory; {hint}")
    missing = sorted(
        f"{skill}.pyz" for skill in SKILLS if not (candidate / f"{skill}.pyz").is_file()
    )
    if missing:
        raise ValueError(
            f"{PREBUILT_ENV}={value!r} is missing archives ({', '.join(missing)}); {hint}"
        )
    return candidate


def _build_one(skill: str, out_dir: Path) -> Path:
    if skill not in SKILLS:
        raise ValueError(f"unknown skill {skill!r}; known: {', '.join(SKILLS)}")
    with tempfile.TemporaryDirectory(prefix=f"easy-cheese-wedge-{skill}-") as tmp:
        result = subprocess.run(
            wedge.wedge_command(
                "build", str(REPO_ROOT / "skills" / skill), "--out", tmp
            ),
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"wedge build failed for {skill}:\n{result.stdout}{result.stderr}"
            )
        payload = cast(dict[str, object], json.loads(result.stdout))
        built = Path(cast(str, payload["path"]))
        target = out_dir / f"{skill}.pyz"
        out_dir.mkdir(parents=True, exist_ok=True)
        _ = shutil.move(built, target)
    return target


def build_archives(out_dir: Path, skills: tuple[str, ...] = SKILLS) -> dict[str, Path]:
    """Build every requested skill archive into ``out_dir`` as ``<skill>.pyz``."""
    def build(skill: str) -> Path:
        return _build_one(skill, out_dir)

    with ThreadPoolExecutor(max_workers=4) as pool:
        paths = list(pool.map(build, skills))
    return dict(zip(skills, paths))


def _cleanup_process_dir() -> None:
    if _process_dir is not None:
        shutil.rmtree(_process_dir, ignore_errors=True)


def archive_path(skill: str) -> Path:
    """The archive to execute for ``skill``: prebuilt, or built once per process."""
    global _process_dir
    prebuilt = prebuilt_dir()
    if prebuilt is not None:
        return prebuilt / f"{skill}.pyz"
    if skill not in _built:
        if _process_dir is None:
            _process_dir = Path(tempfile.mkdtemp(prefix="easy-cheese-archives-"))
            _ = atexit.register(_cleanup_process_dir)
        _built[skill] = _build_one(skill, _process_dir)
    return _built[skill]


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    _ = parser.add_argument("--out-dir", type=Path, required=True)
    _ = parser.add_argument("skills", nargs="*")
    args = parser.parse_args(argv[1:])
    selected = tuple(cast(list[str], args.skills) or SKILLS)
    unknown = sorted(set(selected) - set(SKILLS))
    if unknown:
        parser.error(f"unknown skill(s): {', '.join(unknown)}")
    for skill, path in build_archives(cast(Path, args.out_dir), selected).items():
        print(f"{skill}: {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
