"""Load benchmark cases from ``benchmark/age/cases/<case-id>/case.toml``.

See ``benchmark/age/cases/SCHEMA.md`` for the manifest contract. This module
reads only the four fields the harness needs: ``overlap_area``,
``description``, ``defect.file``, ``defect.line``.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path

from easy_cheese.shared.paths import resolve_repo_root


class CaseNotFoundError(Exception):
    """Raised when a case directory or its manifest is missing."""


@dataclass(frozen=True)
class Case:
    case_id: str
    overlap_area: str
    description: str
    defect_file: str
    defect_line: int
    dir: Path

    @property
    def base_dir(self) -> Path:
        return self.dir / "base"

    @property
    def seed_patch(self) -> Path:
        return self.dir / "seed.patch"


def cases_root(repo_root: Path | str | None = None) -> Path:
    return resolve_repo_root(repo_root) / "benchmark" / "age" / "cases"


def load_case(case_id: str, *, repo_root: Path | str | None = None) -> Case:
    case_dir = cases_root(repo_root) / case_id
    manifest_path = case_dir / "case.toml"
    if not manifest_path.is_file():
        raise CaseNotFoundError(f"no case manifest at {manifest_path}")
    with manifest_path.open("rb") as handle:
        manifest = tomllib.load(handle)
    defect = manifest["defect"]
    return Case(
        case_id=case_id,
        overlap_area=manifest["overlap_area"],
        description=manifest["description"],
        defect_file=defect["file"],
        defect_line=defect["line"],
        dir=case_dir,
    )


def list_case_ids(repo_root: Path | str | None = None) -> list[str]:
    root = cases_root(repo_root)
    if not root.is_dir():
        return []
    return sorted(
        entry.name
        for entry in root.iterdir()
        if entry.is_dir() and (entry / "case.toml").is_file()
    )
