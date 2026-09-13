"""Load benchmark cases from ``benchmark/age/cases/<case-id>/case.toml``.

See ``benchmark/age/cases/SCHEMA.md`` for the manifest contract. This module
reads only the four fields the harness needs: ``overlap_area``,
``description``, ``defect.file``, ``defect.line``.
"""

from __future__ import annotations

import tomllib
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from easy_cheese.shared.paths import resolve_repo_root


class CaseNotFoundError(Exception):
    """Raised when a case directory or its manifest is missing."""


def validate_identifier(value: str, kind: str) -> str:
    """Reject an id that could escape its intended directory via path traversal."""
    if not value or "/" in value or "\\" in value or ".." in value:
        raise ValueError(f"invalid {kind}: {value!r}")
    return value


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


def _str_field(mapping: Mapping[str, object], key: str, case_id: str) -> str:
    value = mapping[key]
    if not isinstance(value, str):
        raise CaseNotFoundError(f"{case_id}: {key} must be a string")
    return value


def _int_field(mapping: Mapping[str, object], key: str, case_id: str) -> int:
    value = mapping[key]
    if not isinstance(value, int):
        raise CaseNotFoundError(f"{case_id}: {key} must be an int")
    return value


def _mapping_field(mapping: Mapping[str, object], key: str, case_id: str) -> Mapping[str, object]:
    value = mapping[key]
    if not isinstance(value, dict):
        raise CaseNotFoundError(f"{case_id}: {key} must be a table")
    return cast(Mapping[str, object], value)


def load_case(case_id: str, *, repo_root: Path | str | None = None) -> Case:
    _ = validate_identifier(case_id, "case_id")
    case_dir = cases_root(repo_root) / case_id
    manifest_path = case_dir / "case.toml"
    if not manifest_path.is_file():
        raise CaseNotFoundError(f"no case manifest at {manifest_path}")
    with manifest_path.open("rb") as handle:
        manifest = cast(Mapping[str, object], tomllib.load(handle))
    defect = _mapping_field(manifest, "defect", case_id)
    return Case(
        case_id=case_id,
        overlap_area=_str_field(manifest, "overlap_area", case_id),
        description=_str_field(manifest, "description", case_id),
        defect_file=_str_field(defect, "file", case_id),
        defect_line=_int_field(defect, "line", case_id),
        dir=case_dir,
    )
