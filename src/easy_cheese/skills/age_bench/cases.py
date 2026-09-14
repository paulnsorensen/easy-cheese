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

from easy_cheese.shared import cli
from easy_cheese.shared.paths import resolve_repo_root
from easy_cheese.skills.age_bench.errors import AgeBenchError


class CaseNotFoundError(AgeBenchError):
    """Raised when a case directory or its manifest is missing or malformed."""


def _reject_unsafe_identifier(field: str, value: str) -> None:
    """Reject an id that could escape its intended directory via path traversal."""
    cli.reject_path_segment(field, value)
    if not value or value == ".":
        raise cli.CliError(f"{field} rejects path traversal: {value!r}")


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


def _require_str(
    mapping: Mapping[str, object], key: str, case_id: str, manifest_path: Path
) -> str:
    value = mapping.get(key)
    if value is None:
        raise CaseNotFoundError(f"{case_id}: missing {key} in {manifest_path}")
    if not isinstance(value, str):
        raise CaseNotFoundError(f"{case_id}: {key} must be a string")
    return value


def _require_int(
    mapping: Mapping[str, object], key: str, case_id: str, manifest_path: Path
) -> int:
    value = mapping.get(key)
    if value is None:
        raise CaseNotFoundError(f"{case_id}: missing {key} in {manifest_path}")
    if not isinstance(value, int):
        raise CaseNotFoundError(f"{case_id}: {key} must be an int")
    return value


def _require_mapping(
    mapping: Mapping[str, object], key: str, case_id: str, manifest_path: Path
) -> Mapping[str, object]:
    value = mapping.get(key)
    if value is None:
        raise CaseNotFoundError(f"{case_id}: missing {key} in {manifest_path}")
    if not isinstance(value, dict):
        raise CaseNotFoundError(f"{case_id}: {key} must be a table")
    return cast(Mapping[str, object], value)


def load_case(case_id: str, *, repo_root: Path | str | None = None) -> Case:
    _reject_unsafe_identifier("case_id", case_id)
    case_dir = cases_root(repo_root) / case_id
    manifest_path = case_dir / "case.toml"
    if not manifest_path.is_file():
        raise CaseNotFoundError(f"no case manifest at {manifest_path}")
    try:
        with manifest_path.open("rb") as handle:
            manifest = cast(Mapping[str, object], tomllib.load(handle))
    except tomllib.TOMLDecodeError as exc:
        raise CaseNotFoundError(
            f"{case_id}: invalid TOML in {manifest_path}: {exc}"
        ) from exc
    defect = _require_mapping(manifest, "defect", case_id, manifest_path)
    return Case(
        case_id=case_id,
        overlap_area=_require_str(manifest, "overlap_area", case_id, manifest_path),
        description=_require_str(manifest, "description", case_id, manifest_path),
        defect_file=_require_str(defect, "file", case_id, manifest_path),
        defect_line=_require_int(defect, "line", case_id, manifest_path),
        dir=case_dir,
    )