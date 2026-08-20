#!/usr/bin/env python3
# ships-as: cut.pyz red-gate press.pyz (module)
"""Parse, issue, and replay outside-in RED gate receipts.

The helper deliberately accepts only argv arrays.  Receipt files are read with
the strict shared schema loader and are written with one atomic replace after
all graph, digest, and replay checks have passed.
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from types import SimpleNamespace
from typing import Any, Literal

# A source checkout does not install ``src`` as a package when this file is
# invoked directly.  Bundled execution imports from the archive itself; adding
# its containing directory would let adjacent files shadow archive members.
_MODULE_PATH = Path(__file__).resolve()
_BUNDLE_PATH = next(
    (parent for parent in _MODULE_PATH.parents if parent.suffix == ".pyz"),
    None,
)
if _BUNDLE_PATH is None:
    _SOURCE_ROOT = _MODULE_PATH.parents[1]
    if str(_SOURCE_ROOT) not in sys.path:
        sys.path.insert(0, str(_SOURCE_ROOT))

from easy_cheese_schemas import (  # noqa: E402
    GateDisposition,
    GateMode,
    GateProducer,
    GateReceipt,
    RedKind,
    TestContract,
    load as strict_load,
)
from easy_cheese_schemas.compat import Provenance, SCHEMA_VERSION  # noqa: E402

try:  # bundled zipapp stages the probe as a flat sibling
    import cut_assertion_probe  # noqa: E402
except ModuleNotFoundError:  # pragma: no cover - source checkout package path
    from cut import cut_assertion_probe  # type: ignore[no-redef]  # noqa: E402

try:  # the Cut bundle stages Mold's canonical parser as a flat module
    from mold.taste_test import (  # noqa: E402
        ApplicabilityError as MoldApplicabilityError,
        NotApplicable as MoldNotApplicable,
        is_new_mold_spec,
        parse_gate_applicability as parse_mold_gate_applicability,
    )
except ModuleNotFoundError:  # pragma: no cover - bundled import path
    from taste_test import (  # type: ignore[no-redef]  # noqa: E402
        ApplicabilityError as MoldApplicabilityError,
        NotApplicable as MoldNotApplicable,
        is_new_mold_spec,
        parse_gate_applicability as parse_mold_gate_applicability,
    )

try:  # direct script execution puts this directory on sys.path
    from gate_receipts import GateValidationError, ValidationResult  # noqa: E402
except ModuleNotFoundError:  # pragma: no cover - only unusual import loaders
    from cut.gate_receipts import GateValidationError, ValidationResult  # type: ignore[no-redef]  # noqa: E402


State = Literal["red", "green"]
_PHASE_PLAN_KEYS = frozenset(
    {
        "schema_version",
        "producer",
        "work_id",
        "project_key",
        "production_paths",
        "baseline_checks",
    }
)
_PHASE_CHECK_KEYS = frozenset({"id", "argv", "cwd"})
_PHASE_RESULT_KEYS = frozenset({"id", "observed_exit_code"})
_PHASE_TOKEN_KEYS = frozenset(
    {
        "schema_version",
        "producer",
        "work_id",
        "project_key",
        "project_root",
        "production_paths",
        "baseline_checks",
        "baseline_results",
        "snapshot",
    }
)


@dataclass(frozen=True)
class PhaseTokenResult:
    phase_token_ref: str
    phase_token_sha256: str

    def to_dict(self) -> dict[str, str]:
        return {
            "phase_token_ref": self.phase_token_ref,
            "phase_token_sha256": self.phase_token_sha256,
        }


@dataclass(frozen=True)
class PressBoundaryEvidence:
    completed_cycles: int
    production_changed: bool


@dataclass(frozen=True)
class _PhasePlan:
    producer: GateProducer
    work_id: str
    project_key: str
    production_paths: tuple[str, ...]
    baseline_checks: tuple[dict[str, Any], ...]


@dataclass(frozen=True)
class _PhaseToken:
    producer: GateProducer
    work_id: str
    project_key: str
    project_root: str
    production_paths: tuple[str, ...]
    baseline_checks: tuple[dict[str, Any], ...]
    baseline_results: tuple[dict[str, Any], ...]
    snapshot: dict[str, str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "producer": self.producer.value,
            "work_id": self.work_id,
            "project_key": self.project_key,
            "project_root": self.project_root,
            "production_paths": list(self.production_paths),
            "baseline_checks": [dict(check) for check in self.baseline_checks],
            "baseline_results": [dict(result) for result in self.baseline_results],
            "snapshot": dict(self.snapshot),
        }


_SHELL_MARKERS = frozenset(";|&><`$")
_SHELL_NAMES = frozenset(
    {"sh", "ash", "bash", "dash", "zsh", "fish", "ksh", "csh", "tcsh"}
)
_SHELL_FLAGS = frozenset({"-c", "--command", "/c", "-command", "/command"})
_COMMAND_WRAPPERS = frozenset(
    {"command", "env", "nice", "nohup", "setsid", "timeout", "xargs"}
)
_EXCLUDED_SNAPSHOT_DIRS = frozenset(
    {
        ".git",
        ".cheese",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        "__pycache__",
    }
)
_ACCEPTANCE_ID = re.compile(r"\bAC-[0-9]+(?:[-.][A-Za-z0-9_-]+)?\b")
_HEADING = re.compile(r"^\s*(#{1,6})\s+(.+?)\s*$")


@dataclass(frozen=True)
class _ContractPlan:
    disposition: GateDisposition
    work_class: str
    contracts: tuple[TestContract, ...]
    not_applicable_reason: str | None
    problems: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "disposition": self.disposition.value,
            "work_class": self.work_class,
            "contracts": [contract.to_dict() for contract in self.contracts],
            "not_applicable_reason": self.not_applicable_reason,
        }


@dataclass(frozen=True)
class _Run:
    returncode: int
    output: str
    error: str | None = None
    assertion_origin: bool = False


_PROBE_EVENT_ERROR = "assertion probe event missing or invalid"


@dataclass(frozen=True)
class _ProbeCommand:
    argv: list[str]
    runner: str


_ASSERTION_PROBE_IMPORT_ROOT = str(Path(cut_assertion_probe.__file__).resolve().parent)


_ASSERTION_PROBE_BOOTSTRAP = (
    "import sys\n"
    "root = sys.argv.pop(1)\n"
    "runner = sys.argv[2]\n"
    "if runner == 'pytest':\n"
    "    import pytest\n"
    "elif runner == 'unittest':\n"
    "    import unittest\n"
    "startup_path = list(sys.path)\n"
    "startup_modules = set(sys.modules)\n"
    "missing = object()\n"
    "prior_probe = sys.modules.pop('cut_assertion_probe', missing)\n"
    "prefixes = tuple(\n"
    "    prefix\n"
    "    for prefix in (sys.prefix, sys.base_prefix, sys.exec_prefix, sys.base_exec_prefix)\n"
    "    if prefix\n"
    ")\n"
    "trusted_path = tuple(\n"
    "    path\n"
    "    for path in startup_path\n"
    "    if path and any(\n"
    "        path == prefix or path.startswith(prefix + '/')\n"
    "        for prefix in prefixes\n"
    "    )\n"
    ")\n"
    "sys.path[:] = [root, *trusted_path]\n"
    "try:\n"
    "    worker = __import__('cut_assertion_probe')\n"
    "finally:\n"
    "    sys.path[:] = startup_path\n"
    "    for name in list(sys.modules):\n"
    "        if name not in startup_modules:\n"
    "            del sys.modules[name]\n"
    "    sys.modules.pop('cut_assertion_probe', None)\n"
    "    if prior_probe is not missing:\n"
    "        sys.modules['cut_assertion_probe'] = prior_probe\n"
    "raise SystemExit(worker.main(sys.argv[1:]))\n"
)


@dataclass
class _GuardGraph:
    nodes: dict[str, GateReceipt]
    problems: list[str]
    cut_nodes: list[str]


def _unique(items: Sequence[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(item for item in items if item))


def _unquote(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        return value[1:-1]
    return value


def _parse_frontmatter(text: str) -> dict[str, Any]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    end = next(
        (index for index in range(1, len(lines)) if lines[index].strip() == "---"), None
    )
    if end is None:
        return {}
    result: dict[str, Any] = {}
    nested: dict[str, str] | None = None
    for line in lines[1:end]:
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        indent = len(line) - len(line.lstrip())
        if indent == 0 and ":" in line:
            key, value = line.split(":", 1)
            key = key.strip()
            value = _unquote(value)
            if value:
                result[key] = value
                nested = None
            else:
                nested = {}
                result[key] = nested
            continue
        if nested is not None and indent > 0 and ":" in line:
            key, value = line.split(":", 1)
            nested[key.strip()] = _unquote(value)
    return result


def _acceptance_criteria(text: str) -> dict[str, str]:
    lines = text.splitlines()
    start: int | None = None
    level = 0
    for index, line in enumerate(lines):
        match = _HEADING.match(line)
        if match and match.group(2).strip().lower() in {
            "acceptance",
            "acceptance criteria",
        }:
            start, level = index + 1, len(match.group(1))
            break
    if start is None:
        return {}
    selected = lines[start:]
    if start is not None:
        for index, line in enumerate(selected):
            match = _HEADING.match(line)
            if match and len(match.group(1)) <= level:
                selected = selected[:index]
                break
    criteria: dict[str, str] = {}
    for line in selected:
        match = _ACCEPTANCE_ID.search(line)
        if not match:
            continue
        acceptance_id = match.group(0)
        text_value = line.split(acceptance_id, 1)[1].lstrip(" :-\t")
        criteria.setdefault(acceptance_id, text_value.strip() or acceptance_id)
    return criteria


def _pipe_cells(line: str) -> list[str]:
    value = line.strip()
    if value.startswith("|"):
        value = value[1:]
    if value.endswith("|"):
        value = value[:-1]
    return [cell.strip() for cell in value.split("|")]


def _is_separator_row(cells: Sequence[str]) -> bool:
    return bool(cells) and all(
        re.fullmatch(r":?-{3,}:?", cell.replace(" ", "")) for cell in cells
    )


def _contract_table(text: str) -> tuple[list[dict[str, str]], list[str], bool]:
    lines = text.splitlines()
    rows: list[dict[str, str]] = []
    problems: list[str] = []
    heading_index: int | None = None
    heading_level = 0
    for index, line in enumerate(lines):
        match = _HEADING.match(line)
        if match and match.group(2).strip().lower() == "test contracts":
            heading_index, heading_level = index, len(match.group(1))
            break
    if heading_index is None:
        return rows, problems, False

    table_lines: list[str] = []
    for line in lines[heading_index + 1 :]:
        heading = _HEADING.match(line)
        if heading and len(heading.group(1)) <= heading_level:
            break
        if "|" in line and line.strip():
            table_lines.append(line)
    if not table_lines:
        return rows, ["Test Contracts table is missing its header and rows"], True

    header = _pipe_cells(table_lines[0])
    normalized = [re.sub(r"[^a-z0-9]+", " ", cell.lower()).strip() for cell in header]
    required = {
        "acceptance": ("acceptance", "acceptance id", "acceptance criterion"),
        "interface": ("interface", "interface referent"),
        "seam": ("outermost stable seam", "stable seam", "seam"),
        "expected_failure": ("expected failure", "failure", "expected witness"),
        "mode": ("mode", "gate mode"),
    }
    optional = {
        "interface_version": ("interface version", "version"),
        "matrix_rows": ("matrix rows", "required matrix rows"),
    }
    indexes: dict[str, int] = {}
    for name, choices in {**required, **optional}.items():
        for choice in choices:
            if choice in normalized:
                indexes[name] = normalized.index(choice)
                break
        if name in required and name not in indexes:
            problems.append(f"Test Contracts table is missing the {name} column")
    if problems:
        return rows, problems, True

    if len(table_lines) < 2 or not _is_separator_row(_pipe_cells(table_lines[1])):
        problems.append("Test Contracts table is missing its separator row")
        data_lines = table_lines[1:]
    else:
        data_lines = table_lines[2:]
    for row_number, line in enumerate(data_lines, start=1):
        cells = _pipe_cells(line)
        if len(cells) < len(header):
            problems.append(f"Test Contracts row {row_number} has too few columns")
            continue
        rows.append({name: cells[indexes[name]].strip() for name in indexes})
    return rows, problems, True


def _infer_contract(acceptance_id: str, statement: str) -> TestContract:
    refs = re.findall(r"`([^`]+)`", statement)
    interface = refs[0] if refs else f"acceptance criterion {acceptance_id}"
    seam = refs[1] if len(refs) > 1 else interface
    expected = f"assertion failed for {acceptance_id}"
    return TestContract(
        acceptance_id=acceptance_id,
        interface=interface,
        seam=seam,
        expected_failure=expected,
        mode=GateMode.TRACER,
        contract_source="inferred",
    )


def _mode(value: str, row_number: int, problems: list[str]) -> GateMode | None:
    normalized = value.strip().lower().strip("`")
    if normalized == GateMode.TRACER.value:
        return GateMode.TRACER
    if normalized == GateMode.CONTRACT_MATRIX.value:
        return GateMode.CONTRACT_MATRIX
    if "tracer" in normalized and "contract-matrix" in normalized:
        problems.append(
            f"Test Contracts row {row_number} has an ambiguous mode {value!r}"
        )
    else:
        problems.append(
            f"Test Contracts row {row_number} has unsupported mode {value!r}"
        )
    return None


def _split_matrix_rows(value: str) -> list[str]:
    return [
        row.strip().strip("`")
        for row in re.split(r"\s*(?:<br\s*/?>|[,;])\s*", value, flags=re.I)
        if row.strip().strip("`")
    ]


def _parse_declared_spec(path: Path) -> _ContractPlan:
    try:
        applicability = parse_mold_gate_applicability(
            path,
            require_ui_surface=is_new_mold_spec(path),
        )
    except MoldApplicabilityError as exc:
        return _ContractPlan(
            GateDisposition.RED,
            "behavior",
            (),
            None,
            _unique(exc.problems),
        )
    if isinstance(applicability, MoldNotApplicable):
        return _ContractPlan(
            GateDisposition.NOT_APPLICABLE,
            applicability.work_class,
            (),
            applicability.reason,
            (),
        )
    contracts = tuple(
        TestContract(
            acceptance_id=contract.acceptance_id,
            interface=contract.interface,
            seam=contract.seam,
            expected_failure=contract.expected_failure,
            mode=GateMode(contract.mode),
            contract_source=contract.contract_source,
            interface_version=contract.interface_version,
            matrix_rows=list(contract.matrix_rows),
        )
        for contract in applicability.contracts
        if contract.mode != "guard"
    )
    return _ContractPlan(
        GateDisposition.RED,
        applicability.work_class,
        contracts,
        None,
        (),
    )


def _parse_spec(spec: Path | str) -> _ContractPlan:
    path = Path(spec)
    problems: list[str] = []
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        return _ContractPlan(
            GateDisposition.RED,
            "behavior",
            (),
            None,
            (f"cannot read spec {path}: {exc}",),
        )

    frontmatter = _parse_frontmatter(text)
    declaration = frontmatter.get("gate_applicability")
    if declaration is not None and not isinstance(declaration, Mapping):
        problems.append("gate_applicability must be a mapping")
        declaration = {}
    declaration = declaration if isinstance(declaration, Mapping) else None
    if declaration is not None:
        return _parse_declared_spec(path)
    disposition_value = (
        str(declaration.get("disposition", "")).strip() if declaration else ""
    )
    work_class = str(declaration.get("work_class", "")).strip() if declaration else ""
    reason_value = declaration.get("reason") if declaration else None
    if disposition_value == "red-required":
        disposition_value = GateDisposition.RED.value
    rows, table_problems, has_table = _contract_table(text)
    problems.extend(table_problems)
    criteria = _acceptance_criteria(text)
    if (
        declaration is not None
        and disposition_value == GateDisposition.RED.value
        and not criteria
    ):
        problems.append(
            "red-required spec Acceptance section has no stable acceptance IDs"
        )

    contracts: list[TestContract] = []
    if has_table:
        for row_number, row in enumerate(rows, start=1):
            acceptance_cell = row.get("acceptance", "").strip()
            acceptance_ids = _ACCEPTANCE_ID.findall(acceptance_cell)
            residue = _ACCEPTANCE_ID.sub("", acceptance_cell)
            if not acceptance_ids or residue.replace(",", "").replace("`", "").strip():
                problems.append(
                    f"Test Contracts row {row_number} must name one or more stable acceptance IDs"
                )
                continue
            mode = _mode(row.get("mode", ""), row_number, problems)
            if mode is None:
                continue
            for acceptance_id in acceptance_ids:
                try:
                    contracts.append(
                        TestContract(
                            acceptance_id=acceptance_id,
                            interface=row.get("interface", ""),
                            seam=row.get("seam", ""),
                            expected_failure=row.get("expected_failure", ""),
                            mode=mode,
                            contract_source="approved",
                            interface_version=(
                                row.get("interface_version", "").strip() or None
                            ),
                            matrix_rows=_split_matrix_rows(row.get("matrix_rows", "")),
                        )
                    )
                except (TypeError, ValueError) as exc:
                    problems.append(
                        f"Test Contracts row {row_number} is invalid: {exc}"
                    )
    elif declaration is None:
        if criteria:
            for acceptance_id, statement in criteria.items():
                contracts.append(_infer_contract(acceptance_id, statement))
        else:
            problems.append("legacy spec has no acceptance IDs to infer")
    elif disposition_value == GateDisposition.RED.value:
        problems.append("red-required spec is missing its Test Contracts table")

    ids = [contract.acceptance_id for contract in contracts]
    for acceptance_id in ids:
        if ids.count(acceptance_id) > 1:
            problems.append(f"Test Contracts maps {acceptance_id} more than once")
    if criteria and has_table:
        missing = sorted(set(criteria) - set(ids))
        extra = sorted(set(ids) - set(criteria))
        if missing:
            problems.append(
                f"Test Contracts is missing acceptance IDs: {', '.join(missing)}"
            )
        if extra:
            problems.append(
                f"Test Contracts has IDs without acceptance criteria: {', '.join(extra)}"
            )

    if not disposition_value:
        # A table without the new declaration is treated as an old behavior
        # spec; a no-table document follows the same legacy inference path.
        disposition_value = GateDisposition.RED.value
        work_class = work_class or "behavior"
    if not work_class:
        work_class = (
            "behavior" if disposition_value == GateDisposition.RED.value else ""
        )

    valid_classes = {
        "behavior",
        "docs-only",
        "refactor-only",
        "test-only",
        "appearance-only",
    }
    if disposition_value not in {member.value for member in GateDisposition}:
        problems.append(
            f"gate_applicability.disposition is unsupported: {disposition_value!r}"
        )
        disposition = GateDisposition.RED
    else:
        disposition = GateDisposition(disposition_value)
    if work_class not in valid_classes:
        problems.append(f"gate_applicability.work_class is unsupported: {work_class!r}")

    if disposition is GateDisposition.RED:
        if work_class != "behavior":
            problems.append("red-required is valid only with work_class: behavior")
        if not contracts:
            problems.append("red-required requires at least one Test Contract")
    else:
        if work_class not in {
            "docs-only",
            "refactor-only",
            "test-only",
            "appearance-only",
        }:
            problems.append("not-applicable requires a closed non-behavior work_class")
        if contracts or has_table:
            problems.append("not-applicable receipts cannot carry Test Contracts")
        if not isinstance(reason_value, str) or not reason_value.strip():
            problems.append("not-applicable requires a non-empty reason")

    reason = None
    if disposition is GateDisposition.NOT_APPLICABLE and isinstance(reason_value, str):
        reason = reason_value.strip() or None
    return _ContractPlan(
        disposition,
        work_class,
        tuple(contracts),
        reason,
        _unique(problems),
    )


def parse_gate_applicability(spec: Path | str) -> _ContractPlan:
    """Parse the declaration and Test Contracts in ``spec``.

    The private plan keeps parser details out of the published receipt schema;
    callers receive a plan only after all parser diagnostics have been
    accumulated, and invalid plans raise the same error used by ``contracts``.
    """
    plan = _parse_spec(spec)
    if plan.problems:
        raise GateValidationError(plan.problems)
    return plan


def _load_mapping(
    source: Path | str | Mapping[str, Any] | GateReceipt,
) -> tuple[dict[str, Any] | None, list[str]]:
    if isinstance(source, GateReceipt):
        return source.to_dict(), []
    if isinstance(source, Mapping):
        return dict(source), []
    path = Path(source)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return None, [f"cannot read JSON receipt {path}: {exc}"]
    if not isinstance(raw, dict):
        return None, [f"receipt root must be a mapping, not {type(raw).__name__}"]
    return raw, []


def _load_receipt(
    source: Path | str | Mapping[str, Any] | GateReceipt,
) -> tuple[GateReceipt | None, list[str], Provenance | None]:
    raw, problems = _load_mapping(source)
    if raw is None:
        return None, problems, None
    loaded = strict_load(raw, GateReceipt, strict=True)
    problems.extend(loaded.problems)
    if loaded.provenance is not Provenance.CURRENT:
        problems.append(
            f"GateReceipt schema provenance is unsafe: {loaded.provenance.name.lower()}"
        )
    return loaded.value, problems, loaded.provenance


def _path_inside(
    root: Path, value: str | Path, label: str
) -> tuple[Path | None, str | None]:
    try:
        raw_value = os.fspath(value)
    except TypeError:
        return None, f"{label} must be a path: {value!r}"
    if not raw_value:
        return None, f"{label} must not be empty"
    try:
        raw_path = Path(raw_value)
        lexical = Path(
            os.path.abspath(raw_path if raw_path.is_absolute() else root / raw_path)
        )
        resolved = lexical.resolve(strict=False)
        resolved.relative_to(root)
        relative = lexical.relative_to(root)
        current = root
        for part in relative.parts:
            current /= part
            if current.is_symlink():
                return None, f"{label} uses a symlink path: {value!r}"
    except (OSError, RuntimeError, ValueError):
        return None, f"{label} escapes the project root: {value!r}"
    return resolved, None


def _resolve_spec_reference(
    root: Path, value: str | Path, label: str
) -> tuple[Path | None, str | None]:
    try:
        raw_value = os.fspath(value)
    except TypeError:
        return None, f"{label} must be a path: {value!r}"
    if not raw_value:
        return None, f"{label} must not be empty"
    absolute = False
    try:
        raw_path = Path(raw_value)
        absolute = raw_path.is_absolute()
        if absolute:
            lexical = raw_path
            current = Path(lexical.anchor)
            parts = lexical.parts[1:]
        else:
            lexical = root / raw_path
            current = root
            parts = raw_path.parts
        for part in parts:
            if part in {"", "."}:
                continue
            if part == "..":
                current = current.parent
                if not current.is_relative_to(root) and not absolute:
                    return None, f"{label} escapes the project root: {value!r}"
                continue
            current /= part
            if current.is_symlink():
                return None, f"{label} uses a symlink path: {value!r}"
        path = lexical.resolve(strict=False)
        if not absolute:
            path.relative_to(root)
    except (OSError, RuntimeError, ValueError):
        return None, (
            f"{label} escapes the project root: {value!r}"
            if not absolute
            else f"{label} is invalid: {value!r}"
        )
    if not path.exists():
        return None, f"{label} is missing: {value}"
    if not path.is_file():
        return None, f"{label} is not a regular file: {value}"
    return path, None


def _resolved_executable_name(executable: str, cwd: Path | None) -> str:
    if cwd is None:
        return ""
    try:
        path = Path(executable)
        if path.is_absolute() or len(path.parts) > 1:
            candidate = path if path.is_absolute() else cwd / path
            return candidate.resolve(strict=False).name.lower().removesuffix(".exe")
        located = shutil.which(executable)
        return (
            Path(located).resolve(strict=False).name.lower().removesuffix(".exe")
            if located
            else ""
        )
    except (OSError, RuntimeError):
        return ""


def _validate_argv(
    argv: Sequence[str],
    label: str,
    *,
    cwd: Path | None = None,
) -> list[str]:
    problems: list[str] = []
    if not isinstance(argv, list) or not argv:
        return [f"{label} must be a non-empty argv list"]
    executable = Path(argv[0]).name.lower() if isinstance(argv[0], str) else ""
    executable = executable.removesuffix(".exe")
    executable_names = {executable}
    if isinstance(argv[0], str):
        resolved_name = _resolved_executable_name(argv[0], cwd)
        if resolved_name:
            executable_names.add(resolved_name)
    code_index = next(
        (
            index + 1
            for index, token in enumerate(argv[:-1])
            if any(name.startswith("python") for name in executable_names)
            and token == "-c"
        ),
        None,
    )
    for index, token in enumerate(argv):
        if not isinstance(token, str) or not token:
            problems.append(f"{label}[{index}] must be a non-empty string")
            continue
        if "\x00" in token or "\n" in token or "\r" in token:
            problems.append(f"{label}[{index}] contains unsafe shell syntax")
            continue
        if index != code_index and any(marker in token for marker in _SHELL_MARKERS):
            problems.append(f"{label} contains shell-shaped command syntax")
    shell_indices = [
        index
        for index, token in enumerate(argv)
        if isinstance(token, str)
        and Path(token).name.lower().removesuffix(".exe") in _SHELL_NAMES
    ]
    invokes_shell = bool(executable_names & _SHELL_NAMES)
    if executable_names & {"busybox", "toybox"} and len(argv) > 1:
        applet = argv[1]
        invokes_shell = (
            isinstance(applet, str) and Path(applet).name.lower() in _SHELL_NAMES
        )
    if shell_indices or invokes_shell:
        problems.append(f"{label} invokes a shell interpreter")
        if any(
            isinstance(token, str)
            and (
                token.lower() in _SHELL_FLAGS
                or token.lower().startswith(
                    ("-c", "--command=", "-command=", "/c", "/command=")
                )
            )
            for token in argv[1:]
        ):
            problems.append(f"{label} uses a shell execution flag")
    if executable_names & _COMMAND_WRAPPERS:
        problems.append(f"{label} invokes a command wrapper")
    if (
        isinstance(argv[0], str)
        and len(argv) == 1
        and any(character.isspace() for character in argv[0])
    ):
        problems.append(f"{label} is a shell command string, not argv")
    return problems


def _semantic_errors(
    receipt: GateReceipt, root: Path, label: str = "GateReceipt"
) -> list[str]:
    problems: list[str] = []
    if receipt.schema_version != SCHEMA_VERSION:
        problems.append(
            f"{label}.schema_version {receipt.schema_version} is not current"
        )
    if bool(receipt.phase_token_ref) != bool(receipt.phase_token_sha256):
        problems.append(
            f"{label}.phase_token_ref and phase_token_sha256 must be provided together"
        )
    if receipt.disposition is GateDisposition.NOT_APPLICABLE:
        if receipt.guard_receipt_refs:
            problems.append(f"{label} not-applicable receipt must not have guards")
        if (
            receipt.contracts
            or receipt.baseline_checks
            or receipt.cases
            or receipt.protected_files
        ):
            problems.append(
                f"{label} not-applicable receipt must not have RED evidence"
            )
        if not receipt.not_applicable_reason:
            problems.append(f"{label} not-applicable receipt needs a closed reason")
        return problems

    if receipt.producer is GateProducer.CUT and receipt.guard_receipt_refs:
        problems.append(f"{label} initial Cut receipt must have no guards")
    if receipt.producer is GateProducer.PRESS and not receipt.guard_receipt_refs:
        problems.append(f"{label} Press receipt must have a transitive Cut ancestor")

    contract_ids = [contract.acceptance_id for contract in receipt.contracts]
    case_ids = [case.id for case in receipt.cases]
    protected_paths = [entry.path for entry in receipt.protected_files]
    for name, values in (
        ("contract", contract_ids),
        ("case", case_ids),
        ("protected file", protected_paths),
    ):
        duplicates = sorted({value for value in values if values.count(value) > 1})
        for value in duplicates:
            problems.append(f"{label} has duplicate {name} {value!r}")

    contracts = {contract.acceptance_id: contract for contract in receipt.contracts}
    contract_cases: dict[str, list[str]] = {key: [] for key in contracts}
    matrix_rows_seen: dict[str, list[str]] = {key: [] for key in contracts}
    for contract in receipt.contracts:
        if contract.mode is GateMode.TRACER:
            if contract.interface_version is not None or contract.matrix_rows:
                problems.append(
                    f"{label} tracer contract {contract.acceptance_id} cannot carry matrix metadata"
                )
            continue
        if contract.contract_source != "approved":
            problems.append(
                f"{label} matrix contract {contract.acceptance_id} must have approved provenance"
            )
        if contract.interface_version is None:
            problems.append(
                f"{label} matrix contract {contract.acceptance_id} needs an interface version"
            )
        if not contract.matrix_rows:
            problems.append(
                f"{label} matrix contract {contract.acceptance_id} needs declared rows"
            )
        duplicate_rows = sorted(
            {row for row in contract.matrix_rows if contract.matrix_rows.count(row) > 1}
        )
        if duplicate_rows:
            problems.append(
                f"{label} matrix contract {contract.acceptance_id} has duplicate declared rows: "
                + ", ".join(duplicate_rows)
            )

    case_acceptance_union: set[str] = set()
    for index, case in enumerate(receipt.cases, start=1):
        cwd, cwd_problem = _path_inside(root, case.cwd, f"{label}.cases[{index}].cwd")
        if cwd_problem:
            problems.append(cwd_problem)
        else:
            problems.extend(
                _validate_argv(case.argv, f"{label}.cases[{index}].argv", cwd=cwd)
            )
        case_acceptance_union.update(case.acceptance_ids)
        expected_witnesses: set[str] = set()
        bound_modes: set[GateMode] = set()
        for acceptance_id in case.acceptance_ids:
            contract = contracts.get(acceptance_id)
            if contract is None:
                problems.append(
                    f"{label}.cases[{index}] references unknown acceptance ID {acceptance_id!r}"
                )
                continue
            contract_cases.setdefault(acceptance_id, []).append(case.id)
            expected_witnesses.add(contract.expected_failure)
            bound_modes.add(contract.mode)
            if case.seam != contract.seam:
                problems.append(
                    f"{label}.cases[{index}].seam disagrees with contract {acceptance_id}"
                )
            if contract.mode is GateMode.CONTRACT_MATRIX:
                if case.kind is not RedKind.CONTRACT:
                    problems.append(
                        f"{label}.cases[{index}] must be kind contract for matrix contract "
                        f"{acceptance_id}"
                    )
                if case.matrix_row is None:
                    problems.append(
                        f"{label}.cases[{index}] needs matrix_row for contract {acceptance_id}"
                    )
                else:
                    matrix_rows_seen.setdefault(acceptance_id, []).append(
                        case.matrix_row
                    )
        if len(bound_modes) > 1:
            problems.append(
                f"{label}.cases[{index}] cannot mix tracer and contract-matrix bindings"
            )
        if bound_modes == {GateMode.TRACER} and case.matrix_row is not None:
            problems.append(
                f"{label}.cases[{index}] tracer case cannot carry matrix_row"
            )
        if expected_witnesses and set(case.expected_witness) != expected_witnesses:
            problems.append(
                f"{label}.cases[{index}].expected_witness does not match its approved contract failures"
            )
        if receipt.disposition is GateDisposition.RED and case.observed_exit_code == 0:
            problems.append(
                f"{label}.cases[{index}] is not RED: observed exit code is 0"
            )
        if not _witness_matches(case.observed_witness, case.expected_witness):
            problems.append(f"{label}.cases[{index}] observed witness is inconsistent")

    missing = sorted(set(contracts) - case_acceptance_union)
    for acceptance_id in missing:
        problems.append(f"{label} has no case for contract {acceptance_id}")
    misbound = sorted(case_acceptance_union - set(contracts))
    for acceptance_id in misbound:
        problems.append(
            f"{label} cases are misbound to undeclared contract {acceptance_id}"
        )
    for contract in receipt.contracts:
        observed_cases = contract_cases.get(contract.acceptance_id, [])
        if contract.mode is GateMode.TRACER:
            if len(observed_cases) != 1:
                problems.append(
                    f"{label} tracer contract {contract.acceptance_id} must have exactly one case"
                )
            continue
        observed_rows = matrix_rows_seen.get(contract.acceptance_id, [])
        missing_rows = sorted(set(contract.matrix_rows) - set(observed_rows))
        extra_rows = sorted(set(observed_rows) - set(contract.matrix_rows))
        duplicate_rows = sorted(
            {row for row in observed_rows if observed_rows.count(row) > 1}
        )
        if missing_rows:
            problems.append(
                f"{label} matrix contract {contract.acceptance_id} is missing rows: "
                + ", ".join(missing_rows)
            )
        if extra_rows:
            problems.append(
                f"{label} matrix contract {contract.acceptance_id} has unexpected rows: "
                + ", ".join(extra_rows)
            )
        if duplicate_rows:
            problems.append(
                f"{label} matrix contract {contract.acceptance_id} repeats rows: "
                + ", ".join(duplicate_rows)
            )

    for index, check in enumerate(receipt.baseline_checks, start=1):
        cwd, cwd_problem = _path_inside(
            root, check.cwd, f"{label}.baseline_checks[{index}].cwd"
        )
        if cwd_problem:
            problems.append(cwd_problem)
        else:
            problems.extend(
                _validate_argv(
                    check.argv, f"{label}.baseline_checks[{index}].argv", cwd=cwd
                )
            )
    for index, entry in enumerate(receipt.protected_files, start=1):
        _, error = _path_inside(
            root, entry.path, f"{label}.protected_files[{index}].path"
        )
        if error:
            problems.append(error)
    return problems


def _witness_matches(observed: str, expected: Sequence[str]) -> bool:
    return bool(observed.strip()) and all(needle in observed for needle in expected)


def _safe_cwd(root: Path, cwd: str, label: str, problems: list[str]) -> Path | None:
    path, error = _path_inside(root, cwd, label)
    if error:
        problems.append(error)
        return None
    assert path is not None
    if not path.is_dir():
        problems.append(f"{label} does not name an existing directory: {cwd!r}")
        return None
    return path


def _run(
    argv: list[str],
    cwd: Path,
    *,
    env: Mapping[str, str] | None = None,
    pass_fds: tuple[int, ...] = (),
) -> _Run:
    try:
        completed = subprocess.run(
            argv,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            shell=False,
            timeout=120,
            env=env,
            pass_fds=pass_fds,
        )
    except subprocess.TimeoutExpired as exc:
        parts = (
            part.decode(errors="replace") if isinstance(part, bytes) else part
            for part in (exc.stdout, exc.stderr)
            if part
        )
        return _Run(124, "\n".join(parts).strip(), "command timed out")
    except (OSError, subprocess.SubprocessError) as exc:
        return _Run(127, "", str(exc))
    output_parts = [
        part.rstrip() for part in (completed.stdout, completed.stderr) if part
    ]
    return _Run(completed.returncode, "\n".join(output_parts).strip())


def _python_case_command(
    argv: list[str],
    cwd: Path,
    probe_fd: int,
) -> _ProbeCommand | None:
    executable_names = {
        Path(argv[0]).name.lower().removesuffix(".exe"),
        _resolved_executable_name(argv[0], cwd),
    }
    if not any(name.startswith("python") for name in executable_names):
        return None
    prefix = [
        argv[0],
        "-c",
        _ASSERTION_PROBE_BOOTSTRAP,
        _ASSERTION_PROBE_IMPORT_ROOT,
        str(probe_fd),
    ]
    if len(argv) >= 3 and argv[1] == "-c":
        return _ProbeCommand(
            [*prefix, "code", argv[0], argv[2], *argv[3:]],
            "code",
        )
    if len(argv) >= 3 and argv[1:3] == ["-m", "pytest"]:
        return _ProbeCommand(
            [*prefix, "pytest", argv[0], *argv[3:]],
            "pytest",
        )
    if len(argv) >= 3 and argv[1:3] == ["-m", "unittest"]:
        return _ProbeCommand(
            [*prefix, "unittest", argv[0], *argv[3:]],
            "unittest",
        )
    if len(argv) >= 2 and argv[1].endswith(".py"):
        return _ProbeCommand(
            [*prefix, "script", argv[0], argv[1], *argv[2:]],
            "script",
        )
    return None


def _run_case(argv: list[str], cwd: Path) -> _Run:
    try:
        read_fd, write_fd = os.pipe()
    except OSError as exc:
        return _Run(127, "", f"cannot create assertion probe: {exc}")
    command = _python_case_command(argv, cwd, write_fd)
    if command is None:
        os.close(read_fd)
        os.close(write_fd)
        return _Run(
            127,
            "",
            "unsupported assertion-proof runner profile; use direct Python, "
            "python -m pytest, or python -m unittest",
        )

    try:
        run = _run(
            command.argv,
            cwd,
            pass_fds=(write_fd,),
        )
    finally:
        os.close(write_fd)

    os.set_blocking(read_fd, False)
    try:
        probe = os.read(read_fd, cut_assertion_probe.MAX_EVENT_BYTES + 1)
    except BlockingIOError:
        probe = b""
    finally:
        os.close(read_fd)
    event = cut_assertion_probe.ProbeEvent.decode(probe, command.runner)
    error = run.error
    if event is None and error is None:
        error = _PROBE_EVENT_ERROR
    return _Run(
        run.returncode,
        run.output,
        error,
        event.assertion_origin if event is not None else False,
    )


def _looks_harness_failure(run: _Run) -> bool:
    if run.error or run.returncode == 127:
        return True
    if run.assertion_origin:
        return False
    output = run.output.lower()
    markers = (
        "error collecting",
        "collection error",
        "syntaxerror",
        "modulenotfounderror",
        "filenotfounderror",
        "no such file or directory",
        "command not found",
        "fixture '",
    )
    if any(marker in output for marker in markers):
        return True
    return "traceback (most recent call last)" in output


def _canonical_witness(output: str, expected: Sequence[str]) -> str:
    normalized = "\n".join(
        line.rstrip() for line in output.replace("\r\n", "\n").splitlines()
    ).strip()
    matches = [needle for needle in expected if needle in normalized]
    return "\n".join(dict.fromkeys(matches)) or normalized


def _replay_baselines(
    receipt: GateReceipt, root: Path, problems: list[str], label: str
) -> None:
    for index, check in enumerate(receipt.baseline_checks, start=1):
        argv_problems = _validate_argv(
            check.argv, f"{label}.baseline_checks[{index}].argv"
        )
        problems.extend(argv_problems)
        if argv_problems:
            continue
        cwd = _safe_cwd(
            root, check.cwd, f"{label}.baseline_checks[{index}].cwd", problems
        )
        if cwd is None:
            continue
        resolved_argv_problems = _validate_argv(
            check.argv,
            f"{label}.baseline_checks[{index}].argv",
            cwd=cwd,
        )
        problems.extend(resolved_argv_problems)
        if resolved_argv_problems:
            continue
        run = _run(check.argv, cwd)
        if run.returncode != 0:
            suffix = f": {run.error}" if run.error else ""
            problems.append(
                f"{label}.baseline_checks[{index}] is not GREEN (exit {run.returncode}){suffix}"
            )


def _replay_cases(
    receipt: GateReceipt,
    root: Path,
    desired: Literal["red", "green"],
    problems: list[str],
    label: str,
    claims: bool = False,
) -> dict[str, _Run]:
    runs: dict[str, _Run] = {}
    for index, case in enumerate(receipt.cases, start=1):
        argv_problems = _validate_argv(case.argv, f"{label}.cases[{index}].argv")
        problems.extend(argv_problems)
        if argv_problems:
            continue
        cwd = _safe_cwd(root, case.cwd, f"{label}.cases[{index}].cwd", problems)
        if cwd is None:
            continue
        resolved_argv_problems = _validate_argv(
            case.argv,
            f"{label}.cases[{index}].argv",
            cwd=cwd,
        )
        problems.extend(resolved_argv_problems)
        if resolved_argv_problems:
            continue
        run = _run_case(case.argv, cwd)
        runs[case.id] = run
        if run.error == _PROBE_EVENT_ERROR:
            problems.append(
                f"{label}.cases[{index}] failed in the harness: {run.error}"
            )
        elif desired == "red":
            if run.returncode == 0:
                problems.append(f"{label}.cases[{index}] did not fail RED (exit 0)")
            elif _looks_harness_failure(run):
                suffix = f": {run.error}" if run.error else ""
                problems.append(
                    f"{label}.cases[{index}] failed in the harness, not its declared witness{suffix}"
                )
            elif not run.assertion_origin:
                problems.append(
                    f"{label}.cases[{index}] failed without assertion-origin evidence"
                )
            elif not _witness_matches(run.output, case.expected_witness):
                problems.append(
                    f"{label}.cases[{index}] failed without its declared witness"
                )
        elif run.returncode != 0:
            suffix = f": {run.error}" if run.error else ""
            problems.append(
                f"{label}.cases[{index}] is not GREEN (exit {run.returncode}){suffix}"
            )
        if claims and run.returncode != case.observed_exit_code:
            problems.append(
                f"{label}.cases[{index}] observed exit claim {case.observed_exit_code} disagrees with replay {run.returncode}"
            )
        if claims:
            canonical_witness = _canonical_witness(run.output, case.expected_witness)
            if case.observed_witness != canonical_witness:
                problems.append(
                    f"{label}.cases[{index}] observed witness claim disagrees with replay"
                )
    return runs


def _hash_file(path: Path) -> str | None:
    try:
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
    except OSError:
        return None
    return digest.hexdigest()


def _protected_errors(
    receipt: GateReceipt,
    root: Path,
    problems: list[str],
    label: str,
) -> dict[str, str]:
    current: dict[str, str] = {}
    for index, protected in enumerate(receipt.protected_files, start=1):
        path, error = _path_inside(
            root, protected.path, f"{label}.protected_files[{index}].path"
        )
        if error or path is None:
            problems.append(
                error or f"{label}.protected_files[{index}] has an invalid path"
            )
            continue
        digest = _hash_file(path)
        if digest is None:
            problems.append(
                f"{label}.protected_files[{index}] is missing: {protected.path}"
            )
            continue
        current[protected.path] = digest
        if digest != protected.sha256.removeprefix("sha256:").lower():
            problems.append(f"{label}.protected_files[{index}] digest is stale")
    return current


def _symlink_target_fingerprint(path: Path) -> str:
    try:
        target = path.resolve(strict=False)
        metadata = target.stat()
        mode = stat.S_IMODE(metadata.st_mode)
        if stat.S_ISREG(metadata.st_mode):
            digest = _hash_file(target)
            return f"file:{digest or 'unreadable'}:mode:{mode:o}"
        if stat.S_ISDIR(metadata.st_mode):
            return f"directory:mode:{mode:o}"
        return f"other:mode:{mode:o}"
    except OSError:
        return "missing"


def _snapshot(
    root: Path,
    ignored: set[Path],
    problems: list[str] | None = None,
    label: str = "production-tree",
) -> dict[str, str]:
    snapshot: dict[str, str] = {}
    ignored_keys: set[str] = set()
    for ignored_path in ignored:
        try:
            ignored_keys.add(
                Path(os.path.abspath(ignored_path)).relative_to(root).as_posix()
            )
        except ValueError:
            continue

    def report(message: str) -> None:
        if problems is not None:
            problems.append(message)

    def walk(directory: Path, prefix: tuple[str, ...]) -> None:
        try:
            with os.scandir(directory) as iterator:
                entries = sorted(iterator, key=lambda entry: entry.name)
        except OSError as exc:
            report(f"{label} cannot walk {directory.relative_to(root)}: {exc}")
            return
        for entry in entries:
            relative = "/".join((*prefix, entry.name))
            if entry.name in _EXCLUDED_SNAPSHOT_DIRS or relative in ignored_keys:
                continue
            try:
                path = Path(entry.path)
                metadata = entry.stat(follow_symlinks=False)
                mode = stat.S_IMODE(metadata.st_mode)
                if entry.is_symlink():
                    resolved_target = path.resolve(strict=False)
                    if resolved_target.is_dir():
                        report(
                            f"{label} does not support directory symlink: {relative}"
                        )
                        continue
                    target = _symlink_target_fingerprint(path)
                    snapshot[relative] = (
                        f"symlink:{os.readlink(entry.path)}:mode:{mode:o}:target:{target}"
                    )
                elif entry.is_dir(follow_symlinks=False):
                    snapshot[f"{relative}/"] = f"directory:mode:{mode:o}"
                    walk(path, (*prefix, entry.name))
                elif entry.is_file(follow_symlinks=False):
                    digest = _hash_file(path)
                    if digest is None:
                        report(f"{label} cannot fingerprint {relative}")
                    else:
                        snapshot[relative] = f"file:{digest}:mode:{mode:o}"
                else:
                    report(f"{label} unsupported filesystem entry: {relative}")
            except OSError as exc:
                report(f"{label} cannot fingerprint {relative}: {exc}")

    if root.exists():
        walk(root, ())
    return snapshot


def _path_is_beneath(relative: str, roots: Sequence[str]) -> bool:
    path = relative.rstrip("/")
    return any(path == root or path.startswith(f"{root}/") for root in roots)


def _production_symlink_alias(
    relative: str,
    before: str | None,
    after: str | None,
    production_paths: Sequence[str],
) -> bool:
    if before is None or after is None:
        return False
    before_binding, separator, _ = before.rpartition(":target:")
    after_binding, after_separator, _ = after.rpartition(":target:")
    if (
        not separator
        or not after_separator
        or before_binding != after_binding
        or not before_binding.startswith("symlink:")
    ):
        return False
    match = re.fullmatch(r"symlink:(.*):mode:[0-7]+", before_binding)
    if match is None:
        return False
    target = PurePosixPath(match.group(1))
    if target.is_absolute():
        return False
    parts: list[str] = []
    for part in (PurePosixPath(relative).parent / target).parts:
        if part in {"", "."}:
            continue
        if part == "..":
            if not parts:
                return False
            parts.pop()
        else:
            parts.append(part)
    return _path_is_beneath("/".join(parts), production_paths)


def _snapshot_changes(
    before: Mapping[str, str],
    after: Mapping[str, str],
) -> list[str]:
    return sorted(
        path for path in set(before) | set(after) if before.get(path) != after.get(path)
    )


def _production_changes(
    before: Mapping[str, str],
    after: Mapping[str, str],
    production_paths: Sequence[str],
) -> list[str]:
    return sorted(
        path
        for path in set(before) | set(after)
        if before.get(path) != after.get(path)
        and _path_is_beneath(path, production_paths)
    )


def _receipt_fingerprint(path: Path) -> str | None:
    try:
        metadata = path.lstat()
        mode = stat.S_IMODE(metadata.st_mode)
        if stat.S_ISLNK(metadata.st_mode):
            return f"symlink:{os.readlink(path)}:mode:{mode:o}:target:{_symlink_target_fingerprint(path)}"
        if not stat.S_ISREG(metadata.st_mode):
            return None
        digest = _hash_file(path)
        return f"file:{digest}:mode:{mode:o}" if digest else None
    except OSError:
        return None


def _receipt_snapshot(
    paths: Sequence[Path],
    problems: list[str],
    label: str,
) -> dict[str, str]:
    snapshot: dict[str, str] = {}
    for path in sorted(set(paths), key=lambda item: item.as_posix()):
        fingerprint = _receipt_fingerprint(path)
        if fingerprint is None:
            problems.append(f"{label} cannot fingerprint receipt: {path}")
        else:
            snapshot[path.as_posix()] = fingerprint
    return snapshot


def _receipt_changes(before: Mapping[str, str], after: Mapping[str, str]) -> list[str]:
    return sorted(
        path for path in set(before) | set(after) if before.get(path) != after.get(path)
    )


def _history_fingerprint(root: Path, path: Path) -> str:
    record = _read_internal_file(root, path)
    if record is None:
        return "missing"
    payload, mode = record
    return f"file:{hashlib.sha256(payload).hexdigest()}:mode:{mode:o}"


def _spec_identity(
    receipt: GateReceipt,
    root: Path,
    problems: list[str],
    label: str,
    *,
    required: bool = False,
) -> None:
    if bool(receipt.spec_ref) != bool(receipt.spec_sha256):
        problems.append(f"{label} spec_ref and spec_sha256 must be provided together")
        return
    if not receipt.spec_ref:
        if required:
            problems.append(
                f"{label} spec_ref and spec_sha256 are required for issuance"
            )
        return
    path, error = _resolve_spec_reference(root, receipt.spec_ref, f"{label}.spec_ref")
    if error or path is None:
        problems.append(error or f"{label}.spec_ref is invalid")
        return
    digest = _hash_file(path)
    if digest is None:
        problems.append(f"{label}.spec_ref cannot be fingerprinted: {receipt.spec_ref}")
        return
    expected_digest = receipt.spec_sha256.removeprefix("sha256:").lower()
    if digest != expected_digest:
        problems.append(f"{label}.spec_sha256 is stale")
    plan = _parse_spec(path)
    problems.extend(f"{label}.spec_ref: {problem}" for problem in plan.problems)
    if plan.problems:
        return
    if receipt.disposition is not plan.disposition:
        problems.append(f"{label}.disposition does not match spec contracts")
    expected_contracts = tuple(contract.to_dict() for contract in plan.contracts)
    actual_contracts = tuple(contract.to_dict() for contract in receipt.contracts)
    if actual_contracts != expected_contracts:
        problems.append(f"{label}.contracts do not match the exact spec contracts")
    if (
        receipt.disposition is GateDisposition.NOT_APPLICABLE
        and receipt.not_applicable_reason != plan.not_applicable_reason
    ):
        problems.append(
            f"{label}.not_applicable_reason does not match the exact spec reason"
        )


def _resolve_guard(root: Path, reference: str, problems: list[str]) -> Path | None:
    path, error = _path_inside(root, reference, "guard receipt reference")
    if error or path is None:
        problems.append(error or f"invalid guard receipt reference: {reference!r}")
        return None
    if not path.is_file():
        problems.append(f"guard receipt is missing: {reference}")
        return None
    return path


def _guard_graph(root_receipt: GateReceipt, root: Path) -> _GuardGraph:
    graph = _GuardGraph({}, [], [])
    visiting: list[tuple[str, str]] = []

    def duplicate_refs(receipt: GateReceipt, label: str) -> None:
        seen: set[str] = set()
        duplicates: list[str] = []
        for reference in receipt.guard_receipt_refs:
            path, error = _path_inside(root, reference, "guard receipt reference")
            key = path.as_posix() if path is not None and error is None else reference
            if key in seen and reference not in duplicates:
                duplicates.append(reference)
            seen.add(key)
        for reference in duplicates:
            graph.problems.append(
                f"{label} has duplicate guard receipt reference: {reference}"
            )

    def visit(reference: str) -> None:
        path = _resolve_guard(root, reference, graph.problems)
        if path is None:
            return
        key = path.as_posix()
        cycle_start = next(
            (
                index
                for index, (active_key, _) in enumerate(visiting)
                if active_key == key
            ),
            None,
        )
        if cycle_start is not None:
            chain = [active_reference for _, active_reference in visiting[cycle_start:]]
            graph.problems.append(
                f"guard graph is cyclic: {' -> '.join([*chain, reference])}"
            )
            return
        if key in graph.nodes:
            return

        visiting.append((key, reference))
        try:
            guard, load_problems, _ = _load_receipt(path)
            graph.problems.extend(
                f"{reference}: {problem}" for problem in load_problems
            )
            if guard is None:
                return
            graph.nodes[key] = guard
            duplicate_refs(guard, reference)
            graph.problems.extend(_semantic_errors(guard, root, reference))
            if guard.work_id != root_receipt.work_id:
                graph.problems.append(f"guard {reference} has a different work_id")
            if guard.spec_ref != root_receipt.spec_ref:
                graph.problems.append(f"guard {reference} has a different spec_ref")
            if guard.spec_sha256 != root_receipt.spec_sha256:
                graph.problems.append(f"guard {reference} has a different spec_sha256")
            _spec_identity(guard, root, graph.problems, reference)
            if guard.project_key != root_receipt.project_key:
                graph.problems.append(f"guard {reference} has a different project_key")
            if guard.disposition is not GateDisposition.RED:
                graph.problems.append(f"guard {reference} is not RED")
            if guard.producer is GateProducer.CUT:
                graph.cut_nodes.append(key)
            for nested in guard.guard_receipt_refs:
                visit(nested)
        finally:
            visiting.pop()

    duplicate_refs(root_receipt, "GateReceipt")
    for reference in root_receipt.guard_receipt_refs:
        visit(reference)
    if root_receipt.producer is GateProducer.PRESS:
        if not graph.cut_nodes:
            graph.problems.append("Press receipt has no transitive Cut ancestor")
        elif len(graph.cut_nodes) != 1:
            graph.problems.append(
                "Press receipt must have exactly one transitive Cut ancestor"
            )
    return graph


def _load_and_check(
    source: Path | str | Mapping[str, Any] | GateReceipt,
    root: Path,
    *,
    require_spec: bool = False,
) -> tuple[GateReceipt | None, list[str], _GuardGraph | None]:
    if isinstance(source, (str, Path)):
        source_path, error = _path_inside(root, source, "receipt input")
        if error or source_path is None:
            return None, [error or "receipt input is invalid"], None
        if not source_path.is_file():
            return None, [f"receipt input is missing: {source}"], None
        source = source_path
    receipt, problems, _ = _load_receipt(source)
    if receipt is None:
        return None, problems, None
    problems.extend(_semantic_errors(receipt, root))
    _spec_identity(receipt, root, problems, "GateReceipt", required=require_spec)
    graph = None
    if receipt.disposition is GateDisposition.RED:
        graph = _guard_graph(receipt, root)
        problems.extend(graph.problems)
    return receipt, problems, graph


def _graph_receipts(graph: _GuardGraph) -> tuple[tuple[str, GateReceipt], ...]:
    return tuple(sorted(graph.nodes.items(), key=lambda item: item[0]))


def _validate_runtime(
    receipt: GateReceipt,
    graph: _GuardGraph | None,
    root: Path,
    state: State,
    problems: list[str],
) -> None:
    if receipt.disposition is GateDisposition.NOT_APPLICABLE:
        return
    _replay_baselines(receipt, root, problems, "GateReceipt")
    desired: Literal["red", "green"] = "red" if state == "red" else "green"
    _replay_cases(receipt, root, desired, problems, "GateReceipt")
    _protected_errors(receipt, root, problems, "GateReceipt")
    if graph is None:
        return
    for reference, guard in _graph_receipts(graph):
        _replay_baselines(guard, root, problems, reference)
        _replay_cases(guard, root, "green", problems, reference)
        _protected_errors(guard, root, problems, reference)


def validate_gate(
    receipt: Path | str | GateReceipt,
    state: State,
) -> ValidationResult:
    """Replay a receipt and all guards in ``state`` without writing anything."""
    problems: list[str] = []
    if state not in {"red", "green"}:
        return ValidationResult(False, (f"state must be red or green, not {state!r}",))
    root = Path.cwd().resolve()
    loaded, load_problems, graph = _load_and_check(receipt, root, require_spec=True)
    problems.extend(load_problems)
    if loaded is None:
        return ValidationResult(False, _unique(problems))
    evidence_receipts = [("GateReceipt", loaded)]
    if graph is not None:
        evidence_receipts.extend(_graph_receipts(graph))
    phase_token_paths: list[Path] = []
    phase_tokens: list[tuple[str, GateReceipt, _PhaseToken]] = []
    spec_paths: list[Path] = []
    for label, evidence_receipt in evidence_receipts:
        if evidence_receipt.phase_token_ref is not None:
            loaded_token, token_path, token_problems = _load_phase_token(
                evidence_receipt.phase_token_ref,
                evidence_receipt,
                root,
                allow_inherited_root=True,
            )
            if label == "GateReceipt":
                problems.extend(token_problems)
            else:
                problems.extend(f"{label}: {problem}" for problem in token_problems)
            if token_path is not None:
                phase_token_paths.append(token_path)
            if loaded_token is not None:
                phase_tokens.append((label, evidence_receipt, loaded_token))
        if evidence_receipt.spec_ref is None:
            continue
        spec_path, spec_error = _resolve_spec_reference(
            root, evidence_receipt.spec_ref, f"{label}.spec_ref"
        )
        if spec_error or spec_path is None:
            problems.append(spec_error or f"{label}.spec_ref is invalid")
        elif spec_path.is_file():
            spec_paths.append(spec_path)
    ignored: set[Path] = set()
    active_path: Path | None = None
    if isinstance(receipt, (str, Path)):
        active_path, _ = _path_inside(root, receipt, "receipt input")
        if active_path is not None:
            ignored.add(active_path)
    receipt_paths = [
        *phase_token_paths,
        *spec_paths,
        *([Path(path) for path in graph.nodes] if graph is not None else []),
    ]
    if active_path is not None:
        receipt_paths.append(active_path)
    receipt_paths = list(dict.fromkeys(receipt_paths))
    receipt_before = _receipt_snapshot(
        receipt_paths, problems, "receipt files before validation"
    )
    allowed_protected = {
        protected.path
        for _, evidence_receipt in evidence_receipts
        for protected in evidence_receipt.protected_files
    }
    before = _snapshot(root, ignored, problems, "production-tree before validation")
    for label, evidence_receipt, loaded_token in phase_tokens:
        problems.extend(
            _phase_replay_errors(
                evidence_receipt,
                loaded_token,
                before,
                label,
                allowed_protected,
            )
        )
    _validate_runtime(loaded, graph, root, state, problems)
    for label, evidence_receipt in evidence_receipts:
        _spec_identity(evidence_receipt, root, problems, label, required=False)
    receipt_after = _receipt_snapshot(
        receipt_paths, problems, "receipt files after validation"
    )
    after = _snapshot(root, ignored, problems, "production-tree after validation")
    for path in _snapshot_changes(before, after):
        problems.append(f"production-tree file changed during validation: {path}")
    for path in _receipt_changes(receipt_before, receipt_after):
        problems.append(f"receipt file changed during validation: {path}")
    return ValidationResult(not problems, _unique(problems), loaded)


def _issue_output_errors(receipt: GateReceipt, output: Path, root: Path) -> list[str]:
    namespace_name = "cut" if receipt.producer is GateProducer.CUT else "press"
    namespace = root / ".cheese" / namespace_name
    problems: list[str] = []
    try:
        output.relative_to(namespace)
    except ValueError:
        problems.append(
            f"receipt output must be beneath project .cheese/{namespace_name}/"
        )
    if output.parent != namespace:
        problems.append(
            f"receipt output must be a direct child of project .cheese/{namespace_name}/"
        )
    if output.suffix != ".json":
        problems.append("receipt output must use the .json extension")
    if output.exists() or output.is_symlink():
        problems.append("receipt output already exists; issuance is append-only")
    return problems


_PRESS_HISTORY_LIMIT = 3


def _press_history_paths(root: Path, receipt: GateReceipt) -> tuple[Path, Path]:
    identity = f"{receipt.project_key}\0{receipt.work_id}".encode()
    key = hashlib.sha256(identity).hexdigest()
    directory = root / ".cheese" / "press-history"
    return directory / f"{key}.json", directory / f"{key}.lock"


def _receipt_identity(receipt: GateReceipt) -> tuple[Any, ...]:
    contracts = tuple(
        json.dumps(contract.to_dict(), sort_keys=True, separators=(",", ":"))
        for contract in receipt.contracts
    )
    return (
        receipt.project_key,
        receipt.work_id,
        receipt.spec_ref,
        receipt.spec_sha256,
        receipt.disposition.value,
        contracts,
    )


def _read_press_history(
    root: Path,
    receipt: GateReceipt,
) -> tuple[tuple[str, ...], list[str]]:
    history_path, _ = _press_history_paths(root, receipt)
    try:
        payload = _read_internal_bytes(root, history_path)
        if payload is None:
            return (), []
        raw = json.loads(payload)
    except (
        GateValidationError,
        OSError,
        UnicodeDecodeError,
        json.JSONDecodeError,
    ) as exc:
        if isinstance(exc, GateValidationError):
            return (), list(exc.problems)
        return (), [f"Press history is malformed: {exc}"]
    if not isinstance(raw, dict):
        return (), ["Press history root must be an object"]
    problems: list[str] = []
    if raw.get("schema_version") != SCHEMA_VERSION:
        problems.append("Press history schema_version is not current")
    if raw.get("project_key") != receipt.project_key:
        problems.append("Press history has a mismatched project_key")
    if raw.get("work_id") != receipt.work_id:
        problems.append("Press history has a mismatched work_id")
    references = raw.get("receipts")
    if not isinstance(references, list) or not all(
        isinstance(item, str) for item in references
    ):
        problems.append("Press history receipts must be a list of paths")
        return (), problems
    if not references:
        problems.append("Press history cannot be empty after a Press receipt")
    if len(references) > _PRESS_HISTORY_LIMIT:
        problems.append("Press history exceeds the three RED observation limit")
    if len(set(references)) != len(references):
        problems.append("Press history contains duplicate receipt paths")
    expected_identity = _receipt_identity(receipt)
    resolved: list[Path] = []
    for index, reference in enumerate(references, start=1):
        path, error = _path_inside(root, reference, f"Press history receipts[{index}]")
        if error or path is None:
            problems.append(
                error or f"Press history receipt path is invalid: {reference}"
            )
            continue
        canonical_reference = path.relative_to(root).as_posix()
        if reference != canonical_reference:
            problems.append(
                f"Press history receipts[{index}] is not canonical: {reference}"
            )
        if not path.is_file():
            problems.append(f"Press history receipt is missing: {reference}")
            continue
        if not path.is_relative_to(root / ".cheese" / "press"):
            problems.append(
                f"Press history receipt is outside .cheese/press: {reference}"
            )
        history_receipt, load_problems, graph = _load_and_check(path, root)
        problems.extend(
            f"Press history {reference}: {problem}" for problem in load_problems
        )
        if history_receipt is None:
            continue
        if history_receipt.producer is not GateProducer.PRESS:
            problems.append(
                f"Press history receipt is not a Press receipt: {reference}"
            )
        if history_receipt.disposition is not GateDisposition.RED:
            problems.append(f"Press history receipt is not RED: {reference}")
        if _receipt_identity(history_receipt) != expected_identity:
            problems.append(
                f"Press history receipt identity does not match: {reference}"
            )
        if graph is None:
            continue
        for prior in resolved:
            if prior.as_posix() not in graph.nodes:
                problems.append(
                    f"Press history receipt omits prior receipt: {prior.relative_to(root).as_posix()}"
                )
        resolved.append(path)
    return tuple(references), problems


def _existing_press_receipts(
    root: Path,
    receipt: GateReceipt,
    excluded: set[Path],
) -> tuple[tuple[str, ...], list[str]]:
    namespace = root / ".cheese" / "press"
    entries: dict[str, _GuardGraph] = {}
    problems: list[str] = []
    if not namespace.exists():
        return (), problems
    for path in sorted(namespace.glob("*.json")):
        try:
            resolved = path.resolve(strict=False)
        except OSError:
            continue
        if resolved in excluded or path.is_symlink() or not path.is_file():
            continue
        existing, load_problems, graph = _load_and_check(path, root, require_spec=True)
        if existing is None:
            continue
        if (
            existing.producer is not GateProducer.PRESS
            or existing.work_id != receipt.work_id
            or existing.project_key != receipt.project_key
            or existing.spec_ref != receipt.spec_ref
            or existing.spec_sha256 != receipt.spec_sha256
        ):
            continue
        if existing.phase_token_ref is not None:
            _, _, token_problems = _load_phase_token(
                existing.phase_token_ref,
                existing,
                root,
                allow_inherited_root=True,
            )
            load_problems.extend(token_problems)
        reference = path.relative_to(root).as_posix()
        if load_problems or graph is None:
            problems.extend(
                f"existing Press receipt {reference}: {problem}"
                for problem in load_problems
            )
            continue
        entries[reference] = graph
    absolute_references = {
        reference: (root / reference).resolve(strict=False).as_posix()
        for reference in entries
    }
    ranked = sorted(
        (
            reference,
            {
                ancestor
                for ancestor, absolute in absolute_references.items()
                if absolute in graph.nodes
            },
        )
        for reference, graph in entries.items()
    )
    ranked.sort(key=lambda item: (len(item[1]), item[0]))
    ordered: list[str] = []
    for reference, ancestors in ranked:
        if ancestors != set(ordered):
            problems.append(
                "immutable Press receipts do not form one ordered repair chain"
            )
            break
        ordered.append(reference)
    return tuple(ordered), problems


@contextmanager
def _internal_directory_fd(root: Path, directory: Path) -> Iterator[int]:
    try:
        parts = directory.relative_to(root).parts
    except ValueError as exc:
        raise GateValidationError(
            (f"internal evidence directory escapes the project: {directory}",)
        ) from exc
    descriptor = os.open(root, os.O_RDONLY | os.O_DIRECTORY)
    try:
        for part in parts:
            try:
                os.mkdir(part, mode=0o700, dir_fd=descriptor)
            except FileExistsError:
                pass
            child = os.open(
                part,
                os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                dir_fd=descriptor,
            )
            os.close(descriptor)
            descriptor = child
        yield descriptor
    except OSError as exc:
        raise GateValidationError(
            (f"internal evidence directory is unsafe: {directory}: {exc}",)
        ) from exc
    finally:
        os.close(descriptor)


def _internal_entry_exists(root: Path, path: Path) -> bool:
    with _internal_directory_fd(root, path.parent) as directory_fd:
        try:
            os.stat(path.name, dir_fd=directory_fd, follow_symlinks=False)
        except FileNotFoundError:
            return False
        return True


def _read_internal_file(root: Path, path: Path) -> tuple[bytes, int] | None:
    with _internal_directory_fd(root, path.parent) as directory_fd:
        try:
            expected = os.stat(
                path.name,
                dir_fd=directory_fd,
                follow_symlinks=False,
            )
        except FileNotFoundError:
            return None
        if not stat.S_ISREG(expected.st_mode):
            raise GateValidationError(
                (f"internal evidence file is unsafe: {path}: not a regular file",)
            )
        try:
            descriptor = os.open(
                path.name,
                os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK,
                dir_fd=directory_fd,
            )
        except OSError as exc:
            raise GateValidationError(
                (f"internal evidence file is unsafe: {path}: {exc}",)
            ) from exc
        with os.fdopen(descriptor, "rb") as stream:
            opened = os.fstat(stream.fileno())
            if (
                not stat.S_ISREG(opened.st_mode)
                or opened.st_dev != expected.st_dev
                or opened.st_ino != expected.st_ino
            ):
                raise GateValidationError(
                    (f"internal evidence file changed while opening: {path}",)
                )
            return stream.read(), stat.S_IMODE(opened.st_mode)


def _read_internal_bytes(root: Path, path: Path) -> bytes | None:
    record = _read_internal_file(root, path)
    return None if record is None else record[0]


def _remove_internal_entry(root: Path, path: Path) -> None:
    with _internal_directory_fd(root, path.parent) as directory_fd:
        try:
            os.unlink(path.name, dir_fd=directory_fd)
        except FileNotFoundError:
            pass


@contextmanager
def _press_history_lock(root: Path, lock_path: Path) -> Iterator[None]:
    with _internal_directory_fd(root, lock_path.parent) as directory_fd:
        try:
            descriptor = os.open(
                lock_path.name,
                os.O_RDWR | os.O_CREAT | os.O_APPEND | os.O_NOFOLLOW,
                mode=0o600,
                dir_fd=directory_fd,
            )
        except OSError as exc:
            raise GateValidationError(
                (f"Press history lock is unsafe: {lock_path}: {exc}",)
            ) from exc
        with os.fdopen(descriptor, "a+", encoding="utf-8") as stream:
            fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def _atomic_internal_write(root: Path, path: Path, payload: bytes) -> None:
    with _internal_directory_fd(root, path.parent) as directory_fd:
        temporary = f".{path.name}.{os.urandom(12).hex()}"
        descriptor = -1
        try:
            descriptor = os.open(
                temporary,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                mode=0o600,
                dir_fd=directory_fd,
            )
            with os.fdopen(descriptor, "wb") as stream:
                descriptor = -1
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(
                temporary,
                path.name,
                src_dir_fd=directory_fd,
                dst_dir_fd=directory_fd,
            )
        except OSError as exc:
            raise GateValidationError(
                (f"cannot atomically write internal evidence {path}: {exc}",)
            ) from exc
        finally:
            if descriptor >= 0:
                os.close(descriptor)
            try:
                os.unlink(temporary, dir_fd=directory_fd)
            except OSError:
                pass


def _atomic_write_bytes(path: Path, payload: bytes) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary = tempfile.mkstemp(
            prefix=f".{path.name}.", dir=path.parent
        )
        try:
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, path)
        finally:
            Path(temporary).unlink(missing_ok=True)
    except OSError as exc:
        raise GateValidationError((f"cannot atomically write {path}: {exc}",)) from exc


def _press_phase_token(
    source: Path | str,
    digest: str,
    receipt: GateReceipt,
    root: Path,
) -> tuple[_PhaseToken | None, Path | None, list[str]]:
    path, error = _path_inside(root, source, "Press phase token")
    if error or path is None:
        return None, path, [error or "Press phase token path is invalid"]
    raw, problems = _read_json_object(path, "Press phase token")
    if raw is None:
        return None, path, problems
    checks = raw.get("baseline_checks")
    results = raw.get("baseline_results")
    if (
        not isinstance(checks, list)
        or not isinstance(results, list)
        or len(checks) != len(results)
    ):
        return None, path, ["Press phase token has invalid baseline evidence"]
    baseline_checks: list[SimpleNamespace] = []
    for check, result in zip(checks, results, strict=True):
        if not isinstance(check, dict) or not isinstance(result, dict):
            return None, path, ["Press phase token has invalid baseline evidence"]
        baseline_checks.append(
            SimpleNamespace(
                id=check.get("id"),
                argv=tuple(check.get("argv", ())),
                cwd=check.get("cwd"),
                observed_exit_code=result.get("observed_exit_code"),
            )
        )
    binding = SimpleNamespace(
        producer=GateProducer.PRESS,
        work_id=receipt.work_id,
        project_key=receipt.project_key,
        phase_token_ref=path.relative_to(root).as_posix(),
        phase_token_sha256=digest,
        baseline_checks=tuple(baseline_checks),
    )
    return _load_phase_token(source, binding, root)


def _press_prior_receipt(
    root: Path,
    receipt: GateReceipt,
    existing: tuple[str, ...],
) -> GateReceipt:
    graph = _guard_graph(receipt, root)
    if graph.problems:
        raise GateValidationError(_unique(graph.problems))
    if len(existing) > 1:
        prior_key = (root / existing[-2]).resolve(strict=False).as_posix()
    elif len(graph.cut_nodes) == 1:
        prior_key = graph.cut_nodes[0]
    else:
        raise GateValidationError(
            ("Press RED route has no unique prior receipt for production paths",)
        )
    prior = graph.nodes.get(prior_key)
    if prior is None:
        raise GateValidationError(
            ("Press RED route prior receipt is absent from its guard graph",)
        )
    return prior


def consume_press_boundary(
    outcome: Literal["green", "in_contract_red"],
    current_receipt: Path | str,
    phase_token_ref: Path | str,
    phase_token_sha256: str,
) -> PressBoundaryEvidence:
    """Validate and consume one Press interval before routing it."""
    if outcome not in {"green", "in_contract_red"}:
        raise GateValidationError((f"unsupported Press boundary outcome: {outcome!r}",))
    root = Path.cwd().resolve()
    receipt_path, path_error = _path_inside(root, current_receipt, "current receipt")
    if path_error or receipt_path is None:
        raise GateValidationError((path_error or "current receipt path is invalid",))
    state: State = "green" if outcome == "green" else "red"
    validation = validate_gate(receipt_path, state)
    if not validation.ok or validation.receipt is None:
        raise GateValidationError(
            validation.problems or ("current receipt evidence is invalid",)
        )
    receipt = validation.receipt
    token, token_path, token_problems = _press_phase_token(
        phase_token_ref,
        phase_token_sha256,
        receipt,
        root,
    )
    if token is None or token_path is None or token_problems:
        raise GateValidationError(_unique(token_problems))

    current_reference = receipt_path.relative_to(root).as_posix()
    current_digest = _hash_file(receipt_path)
    if current_digest is None:
        raise GateValidationError(("current receipt cannot be fingerprinted",))
    _, lock_path = _press_history_paths(root, receipt)
    token_digest = phase_token_sha256.removeprefix("sha256:").lower()
    if not re.fullmatch(r"[0-9a-f]{64}", token_digest):
        raise GateValidationError(("phase_token_sha256 must be a SHA-256 digest",))
    route_token_reference = token_path.relative_to(root).as_posix()
    decision_path = root / ".cheese" / "press-decisions" / f"{token_digest}.json"

    with _press_history_lock(root, lock_path):
        journal, journal_problems = _read_press_history(root, receipt)
        existing, existing_problems = _existing_press_receipts(root, receipt, set())
        problems = [*journal_problems, *existing_problems]
        if journal and journal != existing:
            problems.append("Press history does not match immutable Press receipts")
        if existing:
            if current_reference != existing[-1]:
                problems.append(
                    "current receipt is not the latest immutable Press receipt"
                )
        elif receipt.producer is GateProducer.PRESS:
            problems.append(
                "current Press receipt is absent from immutable Press history"
            )
        if outcome == "in_contract_red":
            if receipt.producer is not GateProducer.PRESS:
                problems.append(
                    "an in-contract RED route requires the new Press receipt"
                )
            if (
                receipt.phase_token_ref != route_token_reference
                or receipt.phase_token_sha256 is None
                or receipt.phase_token_sha256.removeprefix("sha256:").lower()
                != token_digest
            ):
                problems.append(
                    "an in-contract RED route must consume the new Press receipt phase token"
                )
        completed_cycles = len(existing) - (1 if outcome == "in_contract_red" else 0)
        if completed_cycles < 0 or completed_cycles > _PRESS_HISTORY_LIMIT:
            problems.append(
                "derived Press repair count is outside the bounded protocol"
            )
        if _internal_entry_exists(root, decision_path):
            problems.append("Press phase token has already been routed")
        if problems:
            raise GateValidationError(_unique(problems))

        inherited_receipt = (
            _press_prior_receipt(root, receipt, existing)
            if outcome == "in_contract_red"
            else receipt
        )
        if (
            inherited_receipt.phase_token_ref is None
            or inherited_receipt.phase_token_sha256 is None
        ):
            raise GateValidationError(
                ("prior receipt has no phase token to bind production paths",)
            )
        inherited_token, _, inherited_problems = _load_phase_token(
            inherited_receipt.phase_token_ref,
            inherited_receipt,
            root,
        )
        if inherited_token is None or inherited_problems:
            raise GateValidationError(_unique(inherited_problems))
        if token.production_paths != inherited_token.production_paths:
            raise GateValidationError(
                ("Press phase token production_paths do not match the prior receipt",)
            )
        production_problems: list[str] = []
        current_snapshot = _snapshot(
            root,
            set(),
            production_problems,
            "Press boundary project tree",
        )
        if production_problems:
            raise GateValidationError(_unique(production_problems))
        production_changed = bool(
            _production_changes(
                token.snapshot,
                current_snapshot,
                inherited_token.production_paths,
            )
        )
        decision = {
            "schema_version": SCHEMA_VERSION,
            "project_key": receipt.project_key,
            "work_id": receipt.work_id,
            "phase_token_ref": route_token_reference,
            "phase_token_sha256": token_digest,
            "current_receipt": current_reference,
            "current_receipt_sha256": current_digest,
            "outcome": outcome,
            "completed_cycles": completed_cycles,
            "production_changed": production_changed,
        }
        _atomic_internal_write(
            root,
            decision_path,
            (json.dumps(decision, indent=2, sort_keys=True) + "\n").encode(),
        )
    return PressBoundaryEvidence(completed_cycles, production_changed)


def _read_json_object(
    path: Path, label: str
) -> tuple[dict[str, Any] | None, list[str]]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return None, [f"cannot read {label} {path}: {exc}"]
    if not isinstance(raw, dict):
        return None, [f"{label} must be a JSON object"]
    return raw, []


def _phase_check(
    raw: object,
    index: int,
    root: Path,
    problems: list[str],
) -> dict[str, Any] | None:
    label = f"phase baseline_checks[{index}]"
    if not isinstance(raw, dict):
        problems.append(f"{label} must be an object")
        return None
    extras = sorted(set(raw) - _PHASE_CHECK_KEYS)
    missing = sorted(_PHASE_CHECK_KEYS - set(raw))
    for key in extras:
        problems.append(f"{label} has unsupported field {key!r}")
    for key in missing:
        problems.append(f"{label}.{key} is required")
    identifier = raw.get("id")
    argv = raw.get("argv")
    cwd = raw.get("cwd")
    if not isinstance(identifier, str) or not identifier.strip():
        problems.append(f"{label}.id must be a non-empty string")
    if (
        not isinstance(argv, list)
        or not argv
        or not all(isinstance(token, str) and token for token in argv)
    ):
        problems.append(f"{label}.argv must be a non-empty list of strings")
    if not isinstance(cwd, str) or not cwd:
        problems.append(f"{label}.cwd must be a non-empty string")
    cwd_path = (
        _safe_cwd(root, cwd, f"{label}.cwd", problems) if isinstance(cwd, str) else None
    )
    if isinstance(argv, list):
        problems.extend(_validate_argv(argv, f"{label}.argv", cwd=cwd_path))
    if extras or missing or not isinstance(identifier, str) or not identifier.strip():
        return None
    if (
        not isinstance(argv, list)
        or not argv
        or not all(isinstance(token, str) and token for token in argv)
        or not isinstance(cwd, str)
        or cwd_path is None
    ):
        return None
    return {"id": identifier, "argv": argv, "cwd": cwd}


def _phase_production_paths(
    raw: object,
    root: Path,
    problems: list[str],
) -> tuple[str, ...]:
    if not isinstance(raw, list) or not raw:
        problems.append("phase plan.production_paths must be a non-empty list")
        return ()
    paths: list[str] = []
    for index, item in enumerate(raw, start=1):
        label = f"phase plan.production_paths[{index}]"
        if not isinstance(item, str) or not item:
            problems.append(f"{label} must be a non-empty relative path")
            continue
        path, error = _path_inside(root, item, label)
        if error or path is None:
            problems.append(error or f"{label} is invalid")
            continue
        relative = path.relative_to(root).as_posix()
        if relative == ".":
            problems.append(f"{label} cannot name the project root")
        elif relative == ".cheese" or relative.startswith(".cheese/"):
            problems.append(f"{label} cannot name gate evidence")
        else:
            paths.append(relative)
    if len(paths) != len(set(paths)):
        problems.append("phase plan.production_paths must not contain duplicates")
    ordered = tuple(sorted(set(paths)))
    for index, left in enumerate(ordered):
        if any(_path_is_beneath(left, (right,)) for right in ordered[:index]):
            problems.append(
                "phase plan.production_paths must not contain overlapping roots"
            )
            break
    return ordered


def _load_phase_plan(
    source: Path | str, root: Path
) -> tuple[_PhasePlan | None, list[str]]:
    path, error = _path_inside(root, source, "phase plan")
    if error or path is None:
        return None, [error or "phase plan path is invalid"]
    if not path.is_file():
        return None, [f"phase plan is missing: {source}"]
    raw, problems = _read_json_object(path, "phase plan")
    if raw is None:
        return None, problems
    for key in sorted(set(raw) - _PHASE_PLAN_KEYS):
        problems.append(f"phase plan has unsupported field {key!r}")
    for key in sorted(_PHASE_PLAN_KEYS - set(raw)):
        problems.append(f"phase plan.{key} is required")
    if raw.get("schema_version") != SCHEMA_VERSION:
        problems.append(f"phase plan.schema_version must be {SCHEMA_VERSION}")
    try:
        producer = GateProducer(raw.get("producer"))
    except (TypeError, ValueError):
        producer = None
        problems.append("phase plan.producer must be cut or press")
    work_id = raw.get("work_id")
    project_key = raw.get("project_key")
    if not isinstance(work_id, str) or not work_id.strip():
        problems.append("phase plan.work_id must be a non-empty string")
    if not isinstance(project_key, str) or not project_key.strip():
        problems.append("phase plan.project_key must be a non-empty string")
    production_paths = _phase_production_paths(
        raw.get("production_paths"), root, problems
    )
    raw_checks = raw.get("baseline_checks")
    checks: list[dict[str, Any]] = []
    if not isinstance(raw_checks, list):
        problems.append("phase plan.baseline_checks must be a list")
    else:
        for index, raw_check in enumerate(raw_checks, start=1):
            check = _phase_check(raw_check, index, root, problems)
            if check is not None:
                checks.append(check)
    identifiers = [check["id"] for check in checks]
    for identifier in sorted(
        {item for item in identifiers if identifiers.count(item) > 1}
    ):
        problems.append(f"phase plan has duplicate baseline check {identifier!r}")
    if (
        problems
        or producer is None
        or not isinstance(work_id, str)
        or not isinstance(project_key, str)
    ):
        return None, problems
    return _PhasePlan(
        producer,
        work_id,
        project_key,
        production_paths,
        tuple(checks),
    ), problems


def _phase_output_errors(producer: GateProducer, output: Path, root: Path) -> list[str]:
    namespace = root / ".cheese" / producer.value
    problems: list[str] = []
    try:
        output.relative_to(namespace)
    except ValueError:
        problems.append(
            f"phase token output must be beneath project .cheese/{producer.value}/"
        )
    if output.suffix != ".json":
        problems.append("phase token output must use the .json extension")
    if output.exists() or output.is_symlink():
        problems.append("phase token output already exists; issuance is append-only")
    return problems


def begin_phase(plan: Path | str, output: Path | str) -> PhaseTokenResult:
    """Run entry baselines and freeze the pre-oracle project state."""
    root = Path.cwd().resolve()
    loaded, problems = _load_phase_plan(plan, root)
    output_path, output_error = _path_inside(root, output, "phase token output")
    if output_error or output_path is None:
        problems.append(output_error or "phase token output is invalid")
    if loaded is None or output_path is None:
        raise GateValidationError(_unique(problems))
    problems.extend(_phase_output_errors(loaded.producer, output_path, root))
    results: list[dict[str, Any]] = []
    for index, check in enumerate(loaded.baseline_checks, start=1):
        run = _run(check["argv"], root / check["cwd"])
        if run.error:
            problems.append(
                f"phase baseline_checks[{index}] could not run: {run.error}"
            )
        if run.returncode != 0:
            problems.append(
                f"phase baseline_checks[{index}] is not green: exit {run.returncode}"
            )
        results.append({"id": check["id"], "observed_exit_code": run.returncode})
    snapshot = _snapshot(root, {output_path}, problems, "phase-entry project tree")
    if problems:
        raise GateValidationError(_unique(problems))
    token = _PhaseToken(
        producer=loaded.producer,
        work_id=loaded.work_id,
        project_key=loaded.project_key,
        project_root=root.as_posix(),
        production_paths=loaded.production_paths,
        baseline_checks=loaded.baseline_checks,
        baseline_results=tuple(results),
        snapshot=snapshot,
    )
    payload = (json.dumps(token.to_dict(), indent=2, sort_keys=True) + "\n").encode()
    _atomic_write_bytes(output_path, payload)
    return PhaseTokenResult(
        phase_token_ref=output_path.relative_to(root).as_posix(),
        phase_token_sha256=hashlib.sha256(payload).hexdigest(),
    )


def _load_phase_token(
    source: Path | str,
    receipt: GateReceipt,
    root: Path,
    *,
    allow_inherited_root: bool = False,
) -> tuple[_PhaseToken | None, Path | None, list[str]]:
    problems: list[str] = []
    path, error = _path_inside(root, source, "phase token")
    if error or path is None:
        return None, None, [error or "phase token path is invalid"]
    if not path.is_file():
        return None, path, [f"phase token is missing: {source}"]
    expected_namespace = root / ".cheese" / receipt.producer.value
    if not path.is_relative_to(expected_namespace):
        problems.append(
            f"phase token must be beneath project .cheese/{receipt.producer.value}/"
        )
    if path.suffix != ".json":
        problems.append("phase token must use the .json extension")
    reference = path.relative_to(root).as_posix()
    if receipt.phase_token_ref != reference:
        problems.append(
            "GateReceipt.phase_token_ref does not match the supplied phase token"
        )
    digest = _hash_file(path)
    expected_digest = (receipt.phase_token_sha256 or "").removeprefix("sha256:").lower()
    if digest is None or digest != expected_digest:
        problems.append("GateReceipt.phase_token_sha256 is stale")
    raw, read_problems = _read_json_object(path, "phase token")
    problems.extend(read_problems)
    if raw is None:
        return None, path, problems
    try:
        token_bytes = path.read_bytes()
    except OSError as exc:
        problems.append(f"phase token cannot be read canonically: {exc}")
    else:
        canonical_bytes = (json.dumps(raw, indent=2, sort_keys=True) + "\n").encode()
        if token_bytes != canonical_bytes:
            problems.append("phase token is not in canonical encoding")
    for key in sorted(set(raw) - _PHASE_TOKEN_KEYS):
        problems.append(f"phase token has unsupported field {key!r}")
    for key in sorted(_PHASE_TOKEN_KEYS - set(raw)):
        problems.append(f"phase token.{key} is required")
    if raw.get("schema_version") != SCHEMA_VERSION:
        problems.append(f"phase token.schema_version must be {SCHEMA_VERSION}")
    try:
        producer = GateProducer(raw.get("producer"))
    except (TypeError, ValueError):
        producer = None
        problems.append("phase token.producer must be cut or press")
    work_id = raw.get("work_id")
    project_key = raw.get("project_key")
    project_root = raw.get("project_root")
    if producer is not receipt.producer:
        problems.append("phase token.producer does not match GateReceipt.producer")
    if work_id != receipt.work_id:
        problems.append("phase token.work_id does not match GateReceipt.work_id")
    if project_key != receipt.project_key:
        problems.append(
            "phase token.project_key does not match GateReceipt.project_key"
        )
    if not isinstance(project_root, str) or not Path(project_root).is_absolute():
        problems.append("phase token.project_root must be an absolute path")
    elif not allow_inherited_root and project_root != root.as_posix():
        problems.append(
            "phase token.project_root does not match the current project root"
        )
    raw_production_paths = raw.get("production_paths")
    production_paths: list[str] = []
    if not isinstance(raw_production_paths, list) or not raw_production_paths:
        problems.append("phase token.production_paths must be a non-empty list")
    else:
        for index, item in enumerate(raw_production_paths, start=1):
            label = f"phase token.production_paths[{index}]"
            if not isinstance(item, str) or not item:
                problems.append(f"{label} must be a non-empty relative path")
                continue
            candidate, error = _path_inside(root, item, label)
            if error or candidate is None:
                problems.append(error or f"{label} is invalid")
                continue
            relative = candidate.relative_to(root).as_posix()
            if (
                relative == "."
                or relative == ".cheese"
                or relative.startswith(".cheese/")
            ):
                problems.append(f"{label} is not a production path")
            else:
                production_paths.append(relative)
        if production_paths != sorted(set(production_paths)):
            problems.append("phase token.production_paths must be sorted and unique")
        for index, left in enumerate(production_paths):
            if any(
                _path_is_beneath(left, (right,)) for right in production_paths[:index]
            ):
                problems.append(
                    "phase token.production_paths must not contain overlapping roots"
                )
                break
    checks_raw = raw.get("baseline_checks")
    checks: list[dict[str, Any]] = []
    if not isinstance(checks_raw, list):
        problems.append("phase token.baseline_checks must be a list")
    else:
        for index, raw_check in enumerate(checks_raw, start=1):
            check = _phase_check(raw_check, index, root, problems)
            if check is not None:
                checks.append(check)
    results_raw = raw.get("baseline_results")
    results: list[dict[str, Any]] = []
    if not isinstance(results_raw, list):
        problems.append("phase token.baseline_results must be a list")
    else:
        for index, raw_result in enumerate(results_raw, start=1):
            label = f"phase token.baseline_results[{index}]"
            if not isinstance(raw_result, dict):
                problems.append(f"{label} must be an object")
                continue
            if set(raw_result) != _PHASE_RESULT_KEYS:
                problems.append(f"{label} must contain only id and observed_exit_code")
                continue
            if not isinstance(raw_result.get("id"), str) or not raw_result["id"]:
                problems.append(f"{label}.id must be a non-empty string")
            if raw_result.get("observed_exit_code") != 0:
                problems.append(f"{label}.observed_exit_code must be 0")
            results.append(dict(raw_result))
    snapshot_raw = raw.get("snapshot")
    snapshot: dict[str, str] = {}
    if not isinstance(snapshot_raw, dict):
        problems.append("phase token.snapshot must be an object")
    else:
        for relative, fingerprint in snapshot_raw.items():
            if (
                not isinstance(relative, str)
                or not relative
                or relative.startswith("/")
                or "\\" in relative
                or ".." in Path(relative).parts
                or relative == ".cheese"
                or relative.startswith(".cheese/")
            ):
                problems.append(f"phase token.snapshot has invalid path {relative!r}")
                continue
            if not isinstance(fingerprint, str) or not re.fullmatch(
                r"(?:file:[0-9a-f]{64}:mode:[0-7]{3,4}|directory:mode:[0-7]{3,4}|"
                r"symlink:[^\r\n]+:mode:[0-7]{3,4}:target:[^\r\n]+)",
                fingerprint,
            ):
                problems.append(
                    f"phase token.snapshot[{relative!r}] has invalid fingerprint"
                )
                continue
            snapshot[relative] = fingerprint
    if [result.get("id") for result in results] != [
        check.get("id") for check in checks
    ]:
        problems.append("phase token baseline result IDs do not match baseline checks")
    receipt_checks = [
        {"id": check.id, "argv": list(check.argv), "cwd": check.cwd}
        for check in receipt.baseline_checks
    ]
    receipt_results = [
        {"id": check.id, "observed_exit_code": check.observed_exit_code}
        for check in receipt.baseline_checks
    ]
    if checks != receipt_checks:
        problems.append("GateReceipt.baseline_checks do not match the phase token")
    if results != receipt_results:
        problems.append("GateReceipt baseline results do not match the phase token")
    if (
        problems
        or producer is None
        or not isinstance(work_id, str)
        or not isinstance(project_key, str)
        or not isinstance(project_root, str)
    ):
        return None, path, problems
    return (
        _PhaseToken(
            producer,
            work_id,
            project_key,
            project_root,
            tuple(production_paths),
            tuple(checks),
            tuple(results),
            snapshot,
        ),
        path,
        problems,
    )


def _is_test_side_path(relative: str) -> bool:
    path = Path(relative)
    test_directories = {"test", "tests", "spec", "specs", "__tests__"}
    if any(part.lower() in test_directories for part in path.parts[:-1]):
        return True
    name = path.name.lower()
    return (
        name == "conftest.py"
        or name.startswith("test_")
        or bool(re.search(r"(?:_test|[.]test|[.]spec)[.][a-z0-9]+$", name))
    )


def _phase_replay_errors(
    receipt: GateReceipt,
    token: _PhaseToken,
    current: Mapping[str, str],
    label: str,
    allowed_protected: set[str],
) -> list[str]:
    problems: list[str] = []
    for changed in _snapshot_changes(token.snapshot, current):
        if _path_is_beneath(
            changed, token.production_paths
        ) or _production_symlink_alias(
            changed,
            token.snapshot.get(changed),
            current.get(changed),
            token.production_paths,
        ):
            continue
        if (
            changed in allowed_protected
            and changed not in token.snapshot
            and changed in current
        ):
            continue
        if (
            changed.endswith("/")
            and changed not in token.snapshot
            and changed in current
            and any(path.startswith(changed) for path in allowed_protected)
        ):
            continue
        problems.append(
            f"{label} oracle dependency changed since phase entry: {changed}"
        )
    return problems


def _phase_entry_errors(
    receipt: GateReceipt,
    token: _PhaseToken,
    root: Path,
) -> list[str]:
    problems: list[str] = []
    allowed_files: set[str] = set()
    for protected in receipt.protected_files:
        if not _is_test_side_path(protected.path):
            problems.append(
                f"GateReceipt protected file is not test-side: {protected.path}"
            )
        if _path_is_beneath(protected.path, token.production_paths):
            problems.append(
                f"GateReceipt protected file overlaps phase production_paths: {protected.path}"
            )
        allowed_files.add(protected.path)
    current = _snapshot(root, set(), problems, "pre-issue project tree")
    for changed in _snapshot_changes(token.snapshot, current):
        if changed in allowed_files:
            if changed not in token.snapshot and changed in current:
                continue
            problems.append(f"project file changed since phase entry: {changed}")
            continue
        if (
            changed.endswith("/")
            and changed not in token.snapshot
            and changed in current
            and any(path.startswith(changed) for path in allowed_files)
        ):
            continue
        problems.append(f"project file changed since phase entry: {changed}")
    return problems


def _issue_press_history(
    receipt: GateReceipt,
    output: Path,
    root: Path,
    graph: _GuardGraph,
    excluded_receipt_paths: set[Path],
) -> GateReceipt:
    history_path, lock_path = _press_history_paths(root, receipt)
    with _press_history_lock(root, lock_path):
        journal_references, journal_problems = _read_press_history(root, receipt)
        existing_references, history_problems = _existing_press_receipts(
            root, receipt, excluded_receipt_paths
        )
        if history_problems:
            raise GateValidationError(history_problems)
        if journal_problems:
            raise GateValidationError(journal_problems)
        registered = set(journal_references)
        existing = set(existing_references)
        for reference in sorted(registered - existing):
            history_problems.append(
                f"Press history names no existing receipt: {reference}"
            )
        if history_problems:
            raise GateValidationError(history_problems)
        references = existing_references
        if len(references) >= _PRESS_HISTORY_LIMIT:
            raise GateValidationError(
                ("Press history has reached the three RED observation limit",)
            )
        missing = []
        for reference in references:
            path, error = _path_inside(root, reference, "Press history receipt")
            if error or path is None or path.as_posix() not in graph.nodes:
                missing.append(reference)
        if missing:
            raise GateValidationError(
                tuple(
                    f"Press candidate omits prior receipt: {reference}"
                    for reference in missing
                )
            )
        output_problems = _issue_output_errors(receipt, output, root)
        if output_problems:
            raise GateValidationError(output_problems)
        previous_payload = _read_internal_bytes(root, history_path)
        output_reference = output.relative_to(root).as_posix()
        payload = {
            "schema_version": 1,
            "project_key": receipt.project_key,
            "work_id": receipt.work_id,
            "receipts": [*references, output_reference],
        }
        spec_problems: list[str] = []
        _spec_identity(receipt, root, spec_problems, "GateReceipt", required=True)
        if spec_problems:
            raise GateValidationError(spec_problems)
        try:
            _atomic_internal_write(
                root,
                history_path,
                (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode(),
            )
            _atomic_write(receipt, output)
        except GateValidationError as exc:
            try:
                if previous_payload is None:
                    _remove_internal_entry(root, history_path)
                else:
                    _atomic_internal_write(root, history_path, previous_payload)
            except GateValidationError as rollback_error:
                raise GateValidationError(
                    (*exc.problems, f"Press history rollback failed: {rollback_error}")
                ) from rollback_error
            raise
    return receipt


def _canonical_receipt(
    receipt: GateReceipt, runs: Mapping[str, _Run]
) -> GateReceipt | None:
    raw = receipt.to_dict()
    for case in raw.get("cases", []):
        run = runs.get(case.get("id"))
        if run is None:
            continue
        case["observed_exit_code"] = run.returncode
        case["observed_witness"] = _canonical_witness(
            run.output, case["expected_witness"]
        )
    loaded = strict_load(raw, GateReceipt, strict=True)
    return loaded.value if not loaded.problems else None


def issue_gate(
    candidate: Path | str | Mapping[str, Any] | GateReceipt,
    output: Path | str,
    phase_token: Path | str,
) -> GateReceipt:
    """Validate and atomically write canonical RED or N/A evidence."""
    root = Path.cwd().resolve()
    output_path, output_error = _path_inside(root, output, "receipt output")
    if output_error or output_path is None:
        raise GateValidationError((output_error or "receipt output is invalid",))
    candidate_path: Path | None = None
    if isinstance(candidate, (str, Path)):
        candidate_path, candidate_error = _path_inside(root, candidate, "receipt input")
        if candidate_error or candidate_path is None:
            raise GateValidationError((candidate_error or "receipt input is invalid",))
        if not candidate_path.is_file():
            raise GateValidationError((f"receipt input is missing: {candidate}",))
    receipt, problems, graph = _load_and_check(candidate, root, require_spec=True)
    if receipt is None:
        raise GateValidationError(problems)
    token, token_path, token_problems = _load_phase_token(phase_token, receipt, root)
    problems.extend(token_problems)
    if token is not None:
        problems.extend(_phase_entry_errors(receipt, token, root))
    evidence_receipts = [("GateReceipt", receipt)]
    if graph is not None:
        evidence_receipts.extend(_graph_receipts(graph))
    guard_token_paths: list[Path] = []
    guard_tokens: list[tuple[str, GateReceipt, _PhaseToken]] = []
    for reference, guard in evidence_receipts[1:]:
        if guard.phase_token_ref is None:
            continue
        loaded_guard_token, guard_token_path, guard_token_problems = _load_phase_token(
            guard.phase_token_ref,
            guard,
            root,
            allow_inherited_root=True,
        )
        problems.extend(f"{reference}: {problem}" for problem in guard_token_problems)
        if guard_token_path is not None:
            guard_token_paths.append(guard_token_path)
        if loaded_guard_token is not None:
            guard_tokens.append((reference, guard, loaded_guard_token))
    problems.extend(_issue_output_errors(receipt, output_path, root))
    if receipt.disposition is GateDisposition.NOT_APPLICABLE:
        if receipt.producer not in {GateProducer.CUT, GateProducer.PRESS}:
            problems.append("not-applicable receipt has an unknown producer")
    else:
        _protected_errors(receipt, root, problems, "GateReceipt")

    ignored = {output_path}
    if candidate_path is not None:
        ignored.add(candidate_path)
    receipt_paths = [
        *guard_token_paths,
        *([Path(path) for path in graph.nodes] if graph is not None else []),
    ]
    if candidate_path is not None:
        receipt_paths.append(candidate_path)
    if token_path is not None:
        receipt_paths.append(token_path)
    for label, evidence_receipt in evidence_receipts:
        if evidence_receipt.spec_ref is None:
            continue
        spec_path, spec_path_error = _resolve_spec_reference(
            root, evidence_receipt.spec_ref, f"{label}.spec_ref"
        )
        if spec_path_error or spec_path is None:
            problems.append(spec_path_error or f"{label}.spec_ref is invalid")
        elif spec_path.is_file():
            receipt_paths.append(spec_path)

    receipt_paths = list(dict.fromkeys(receipt_paths))
    history_path: Path | None = None
    history_before: str | None = None
    if (
        receipt.producer is GateProducer.PRESS
        and receipt.disposition is GateDisposition.RED
    ):
        history_path, _ = _press_history_paths(root, receipt)
        history_before = _history_fingerprint(root, history_path)
    receipt_before = _receipt_snapshot(
        receipt_paths, problems, "receipt files before issue"
    )
    allowed_protected = {
        protected.path
        for _, evidence_receipt in evidence_receipts
        for protected in evidence_receipt.protected_files
    }
    before = _snapshot(root, ignored, problems, "production-tree before issue")
    for reference, guard, loaded_guard_token in guard_tokens:
        problems.extend(
            _phase_replay_errors(
                guard,
                loaded_guard_token,
                before,
                reference,
                allowed_protected,
            )
        )
    active_runs: dict[str, _Run] = {}
    if receipt.disposition is GateDisposition.RED:
        _replay_baselines(receipt, root, problems, "GateReceipt")
        active_runs = _replay_cases(
            receipt, root, "red", problems, "GateReceipt", claims=True
        )
        if graph is not None:
            for reference, guard in _graph_receipts(graph):
                _replay_baselines(guard, root, problems, reference)
                _replay_cases(guard, root, "green", problems, reference)
                _protected_errors(guard, root, problems, reference)
    receipt_after = _receipt_snapshot(
        receipt_paths, problems, "receipt files after issue"
    )
    after = _snapshot(root, ignored, problems, "production-tree after issue")
    for path in _snapshot_changes(before, after):
        problems.append(f"production-tree file changed during issue: {path}")
    for path in _receipt_changes(receipt_before, receipt_after):
        problems.append(f"receipt file changed during issue: {path}")
    if history_path is not None and history_before != _history_fingerprint(
        root, history_path
    ):
        problems.append("Press history changed during issue")
    for label, evidence_receipt in evidence_receipts:
        _spec_identity(evidence_receipt, root, problems, label, required=True)

    canonical = receipt
    if receipt.disposition is GateDisposition.RED and not problems:
        canonical = _canonical_receipt(receipt, active_runs)
        if canonical is None:
            problems.append("canonical receipt evidence failed strict validation")
    problems = list(_unique(problems))
    if problems:
        raise GateValidationError(problems)
    assert canonical is not None

    final_spec_problems: list[str] = []
    _spec_identity(canonical, root, final_spec_problems, "GateReceipt", required=True)
    if final_spec_problems:
        raise GateValidationError(final_spec_problems)
    if (
        canonical.producer is GateProducer.PRESS
        and canonical.disposition is GateDisposition.RED
    ):
        if graph is None:
            raise GateValidationError(("Press receipt has no verified guard graph",))
        excluded_receipt_paths = {
            path for path in (candidate_path, token_path) if path is not None
        }
        return _issue_press_history(
            canonical,
            output_path,
            root,
            graph,
            excluded_receipt_paths,
        )
    _atomic_write(canonical, output_path)
    return canonical


def _atomic_write(receipt: GateReceipt, output: Path) -> None:
    root = Path.cwd().resolve()
    output_path, error = _path_inside(root, output, "receipt output")
    if error or output_path is None:
        raise GateValidationError((error or "receipt output is invalid",))
    for protected in receipt.protected_files:
        protected_path, error = _path_inside(root, protected.path, "protected file")
        if error is None and protected_path == output_path:
            raise GateValidationError(
                (f"receipt output must not overwrite protected file: {protected.path}",)
            )
    payload = json.dumps(receipt.to_dict(), indent=2, sort_keys=True) + "\n"
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary = tempfile.mkstemp(
            prefix=f".{output_path.name}.", dir=output_path.parent
        )
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, output_path)
        finally:
            try:
                Path(temporary).unlink()
            except FileNotFoundError:
                pass
    except OSError as exc:
        raise GateValidationError(
            (f"cannot atomically write receipt {output}: {exc}",)
        ) from exc


def _print_problems(problems: Sequence[str]) -> None:
    for problem in problems:
        print(f"ERROR: {problem}", file=sys.stderr)


def main(argv: Sequence[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args:
        print("usage: red-gate {contracts|begin|issue|validate} ...", file=sys.stderr)
        return 2
    command = args.pop(0)
    try:
        if command == "contracts":
            if len(args) != 1:
                raise GateValidationError(("usage: red-gate contracts <spec>",))
            plan = _parse_spec(Path(args[0]))
            if plan.problems:
                raise GateValidationError(plan.problems)
            print(json.dumps(plan.to_dict(), indent=2, sort_keys=True))
            return 0
        if command == "begin":
            if len(args) != 3 or args[1] != "--out":
                raise GateValidationError(
                    ("usage: red-gate begin <plan> --out <token>",)
                )
            result = begin_phase(Path(args[0]), Path(args[2]))
            print(json.dumps(result.to_dict(), indent=2, sort_keys=True))
            return 0
        if command == "issue":
            if len(args) != 5 or args[1] != "--token" or args[3] != "--out":
                raise GateValidationError(
                    (
                        "usage: red-gate issue <candidate> --token <token> "
                        "--out <receipt>",
                    )
                )
            receipt = issue_gate(Path(args[0]), Path(args[4]), Path(args[2]))
            print(json.dumps(receipt.to_dict(), indent=2, sort_keys=True))
            return 0
        if command == "validate":
            if len(args) != 3 or args[1] != "--state":
                raise GateValidationError(
                    ("usage: red-gate validate <receipt> --state red|green",)
                )
            result = validate_gate(Path(args[0]), args[2])  # type: ignore[arg-type]
            print(json.dumps(result.to_dict(), indent=2, sort_keys=True))
            return 0 if result.ok else 1
        raise GateValidationError((f"unknown red-gate command: {command}",))
    except GateValidationError as exc:
        _print_problems(exc.problems)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
