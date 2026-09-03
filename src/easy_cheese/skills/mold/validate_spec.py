#!/usr/bin/env python3
"""Validator for the current Mold specification requirements.

Lenient acceptance (nothing is rewritten): heading case, heading trailing
punctuation, table cell whitespace, and fence dialect (``` vs ~~~) do not
affect validation; fenced code blocks are invisible to heading and table
detection regardless of dialect.

Markdown shape checks reject missing or duplicate tracked headings, malformed
tables, and rows with the wrong number of cells. Fenced code blocks do not count
as headings or table rows. The parsed frontmatter and table rows are then passed
once to ``MoldSpecDocument``. Its typed validators enforce document invariants.

Legacy acceptance: the default read posture accepts v0.13-era specs without a
Mold provenance marker. It waives only the Test Contracts section, the Grounding
section, and the ``gate_applicability`` block that the current format added.
``--strict`` requires the current format and its provenance marker. The policy
lives once in ``easy_cheese_schemas.spec_format`` so every release channel uses
the same rule.

The generated, dependency-free ``document_rules`` projection supplies the
Markdown shape rules. The attrs-backed schema types supply typed validation.

ERROR:-line accumulation and exit codes follow .github/scripts/validate_wiki.py.
"""

from __future__ import annotations

import argparse
import importlib
import importlib.util
import json
import re
import sys
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any, Protocol, TypedDict, cast

from easy_cheese.shared.document_rules import DOCUMENT_RULES


class _SpecFormatPolicy(Protocol):
    @property
    def notice(self) -> str | None: ...

    def requires_gate_applicability(self) -> bool: ...

    def requires_section(
        self, section_name: str, *, default_required: bool
    ) -> bool: ...


class _SpecFormatPolicyFactory(Protocol):
    def __call__(
        self, frontmatter: Mapping[str, object], *, strict: bool
    ) -> _SpecFormatPolicy: ...


is_hardened_provenance: Callable[[Mapping[str, object]], bool]
spec_format_policy: _SpecFormatPolicyFactory


def _load_local_module(
    module_name: str, module_path: Path, import_error: ImportError
) -> Any:
    """Load a source-local module after an installed package import fails."""
    if not module_path.is_file():
        raise import_error
    module_spec = importlib.util.spec_from_file_location(module_name, module_path)
    if module_spec is None or module_spec.loader is None:
        raise RuntimeError(
            f"cannot load local module from {module_path}"
        ) from import_error
    module = importlib.util.module_from_spec(module_spec)
    sys.modules[module_spec.name] = module
    module_spec.loader.exec_module(module)
    return module


try:
    from easy_cheese_schemas.spec_format import (
        is_hardened_provenance as _is_hardened_provenance,
    )
    from easy_cheese_schemas.spec_format import (
        spec_format_policy as _spec_format_policy,
    )
except ImportError as error:
    spec_format = _load_local_module(
        "_mold_spec_format",
        Path(__file__).parents[3] / "easy_cheese_schemas" / "spec_format.py",
        error,
    )
    _is_hardened_provenance = spec_format.is_hardened_provenance
    _spec_format_policy = spec_format.spec_format_policy

is_hardened_provenance = cast(
    Callable[[Mapping[str, object]], bool], _is_hardened_provenance
)
spec_format_policy = cast(_SpecFormatPolicyFactory, _spec_format_policy)


class _CrossFieldRule(TypedDict):
    description: str
    rule_id: str


class _TableRules(TypedDict):
    columns: list[str]
    per_row: list[str]


class _SectionRules(TypedDict):
    name: str
    optional: bool
    table: _TableRules | None


class _ModeRules(TypedDict):
    cross_field_rules: list[_CrossFieldRule]
    enums: dict[str, list[str]]
    sections: list[_SectionRules]


RULES = cast(_ModeRules, cast(object, DOCUMENT_RULES["mold-spec"]))
SECTIONS = RULES["sections"]
ENUMS = RULES["enums"]
_TEST_CONTRACTS_SECTION = next(s for s in SECTIONS if s["name"] == "Test Contracts")
_TEST_CONTRACTS_TABLE = _TEST_CONTRACTS_SECTION["table"]
assert _TEST_CONTRACTS_TABLE is not None
TABLE_COLUMNS: tuple[str, ...] = tuple(_TEST_CONTRACTS_TABLE["columns"])
_AC_ID_COL = TABLE_COLUMNS.index("Acceptance ID")
_MODE_COL = TABLE_COLUMNS.index("Mode")
_INTERFACE_VERSION_COL = TABLE_COLUMNS.index("Interface version")
_MATRIX_ROWS_COL = TABLE_COLUMNS.index("Matrix rows")

_GROUNDING_SECTION = next(s for s in SECTIONS if s["name"] == "Grounding")
_GROUNDING_TABLE = _GROUNDING_SECTION["table"]
assert _GROUNDING_TABLE is not None
GROUNDING_COLUMNS: tuple[str, ...] = tuple(_GROUNDING_TABLE["columns"])
_PROBE_COL = GROUNDING_COLUMNS.index("Probe")
_OUTCOME_COL = GROUNDING_COLUMNS.index("Outcome")
_EVIDENCE_COL = GROUNDING_COLUMNS.index("Evidence")

_CROSS_FIELD_RULE_IDS: set[str] = {
    rule["rule_id"] for rule in RULES["cross_field_rules"]
}


def _rule_id(rule_id: str) -> str:
    assert rule_id in _CROSS_FIELD_RULE_IDS, (
        f"undeclared cross-field rule id: {rule_id}"
    )
    return rule_id


AC_COVERAGE_RULE = _rule_id("ac-coverage-exactly-once")
TRACER_ROW_RULE = _rule_id("tracer-row-blank-matrix-cells")
CONTRACT_MATRIX_ROW_RULE = _rule_id("contract-matrix-row-requires-both")
NOT_APPLICABLE_RULE = _rule_id("not-applicable-closed-class")

# Each declared probe carries its own cross-field rule id so a skipped wiki
# probe and a skipped explorer delegation fail under distinct identifiers.
PROBE_RULES: dict[str, str] = {
    "wiki": _rule_id("grounding-probe-recorded"),
    "explorer": _rule_id("delegation-digest-recorded"),
}
assert set(PROBE_RULES) == set(ENUMS["grounding_probe"]), (
    "every grounding probe needs a cross-field rule id"
)

HEADING_RE = re.compile(r"^##(?!#)\s+(.+?)\s*$")
ACCEPTANCE_ID_RE = re.compile(r"^-\s*(AC-\d+)\s*:")
DELIMITER_CELL_RE = re.compile(r"^:?-{3,}:?$")


def _canonical_heading(name: str) -> str:
    return name.strip().rstrip(".!?:;").casefold()


def _split_frontmatter(text: str) -> tuple[dict[str, object], str]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, text
    end = next(
        (i for i in range(1, len(lines)) if lines[i].strip() == "---"),
        None,
    )
    if end is None:
        return {}, text
    data = _parse_yaml_block(lines[1:end])
    body = "\n".join(lines[end + 1 :])
    return data, body


def _frontmatter_scalar(value: str) -> object:
    value = value.strip()
    if value in {"{}", "[]"}:
        return {} if value == "{}" else []
    if value.lower() in {"true", "false"}:
        return value.lower() == "true"
    if (value.startswith("{") and value.endswith("}")) or (
        value.startswith("[") and value.endswith("]")
    ):
        try:
            return json.loads(value.replace("'", '"'))
        except json.JSONDecodeError:
            return value.strip('"').strip("'")
    return value.strip('"').strip("'")


def _parse_yaml_block(lines: list[str]) -> dict[str, object]:
    """Parse the scalar and nested-map subset used by Mold frontmatter."""
    data: dict[str, object] = {}
    i = 0
    while i < len(lines):
        line = lines[i]
        if not line.strip() or line.startswith(" ") or line.startswith("-"):
            i += 1
            continue
        if ":" not in line:
            i += 1
            continue
        key, _, value = line.partition(":")
        key = key.strip()
        value = value.strip()
        if value:
            data[key] = _frontmatter_scalar(value)
            i += 1
            continue
        nested: dict[str, object] = {}
        j = i + 1
        while j < len(lines) and (lines[j].startswith("  ") or not lines[j].strip()):
            nested_line = lines[j].strip()
            if nested_line and ":" in nested_line and not nested_line.startswith("-"):
                nk, _, nv = nested_line.partition(":")
                nested[nk.strip()] = _frontmatter_scalar(nv)
            j += 1
        data[key] = nested
        i = j
    return data


def _fence_mask(lines: list[str]) -> list[bool]:
    """True for lines that open, close, or sit inside a fenced code block
    (``` or ~~~, either dialect)."""
    mask = [False] * len(lines)
    delimiter: str | None = None
    for i, line in enumerate(lines):
        stripped = line.strip()
        if delimiter is not None:
            mask[i] = True
            if stripped.startswith(delimiter):
                delimiter = None
            continue
        if stripped.startswith("```") or stripped.startswith("~~~"):
            delimiter = stripped[:3]
            mask[i] = True
    return mask


def _find_sections(body: str) -> tuple[dict[str, list[str]], list[str]]:
    """Map canonical heading name -> section content lines (lenient heading
    match), plus the list of canonical names that appear more than once.
    Fenced lines are invisible to both heading and content detection."""
    lines = body.splitlines()
    fenced = _fence_mask(lines)
    headings: list[tuple[int, str]] = []
    for lineno, line in enumerate(lines):
        if fenced[lineno]:
            continue
        match = HEADING_RE.match(line)
        if match:
            headings.append((lineno, _canonical_heading(match.group(1))))
    found: dict[str, list[str]] = {}
    duplicates: list[str] = []
    for idx, (lineno, name) in enumerate(headings):
        end = headings[idx + 1][0] if idx + 1 < len(headings) else len(lines)
        content = [
            line
            for offset, line in enumerate(lines[lineno + 1 : end])
            if not fenced[lineno + 1 + offset]
        ]
        if name in found:
            duplicates.append(name)
        found[name] = content
    return found, duplicates


def _parse_table(content_lines: list[str]) -> list[list[str]] | None:
    """Parse a GFM-style pipe table, tolerant of cell whitespace. None if absent."""
    table_lines = [line for line in content_lines if line.strip().startswith("|")]
    if len(table_lines) < 2:
        return None

    def cells(line: str) -> list[str]:
        stripped = line.strip().strip("|")
        return [cell.strip() for cell in stripped.split("|")]

    rows = [cells(line) for line in table_lines]
    return rows


def _declared_table_rows(
    content_lines: list[str],
    columns: tuple[str, ...],
    section: str,
    error_id: str,
    path: Path,
    errors: list[str],
) -> list[list[str]]:
    """Parse a declared section table, appending ``error_id`` shape errors.

    Returns only the body rows whose cell count matches ``columns``; a missing
    table or a header that does not match the declared columns yields no rows.
    """
    parsed = _parse_table(content_lines)
    if parsed is None:
        errors.append(
            f"ERROR: {error_id} no table found in {section} section of {path}"
        )
        return []
    header = parsed[0]
    if tuple(header) != columns:
        errors.append(
            f"ERROR: {error_id} {section} table columns {header} do not match the "
            + f"required columns {list(columns)} in {path}"
        )
        return []
    delimiter_row = parsed[1]
    if not delimiter_row or not all(
        DELIMITER_CELL_RE.match(cell) for cell in delimiter_row
    ):
        errors.append(
            f"ERROR: {error_id} {section} table is missing its '---' delimiter "
            + f"row in {path}"
        )
        candidate_rows = parsed[1:]
    else:
        candidate_rows = parsed[2:]
    rows: list[list[str]] = []
    for row in candidate_rows:
        if len(row) != len(columns):
            errors.append(
                f"ERROR: {error_id} {section} row {row} has {len(row)} cells, "
                + f"expected {len(columns)} in {path}"
            )
        else:
            rows.append(row)
    return rows


def _acceptance_ids(content_lines: list[str]) -> list[str]:
    ids: list[str] = []
    for line in content_lines:
        match = ACCEPTANCE_ID_RE.match(line.strip())
        if match:
            ids.append(match.group(1))
    return ids


def _schema_module() -> Any:
    try:
        return importlib.import_module("easy_cheese_schemas.contracts")
    except ImportError as error:
        return _load_local_module(
            "_mold_contracts",
            Path(__file__).parents[3] / "easy_cheese_schemas" / "contracts.py",
            error,
        )


def _matrix_rows(value: str) -> tuple[str, ...]:
    return tuple(
        row.strip()
        for row in re.split(r"\s*(?:<br\s*/?>|[,;])\s*", value, flags=re.I)
        if row.strip()
    )


def _typed_errors(message: str, path: Path) -> tuple[str, ...]:
    if "Test Contracts table must cover" in message:
        return (f"ERROR: {AC_COVERAGE_RULE} {message} in {path}",)
    if "tracer mode" in message:
        return (f"ERROR: {TRACER_ROW_RULE} {message} in {path}",)
    if "contract-matrix mode" in message:
        return (f"ERROR: {CONTRACT_MATRIX_ROW_RULE} {message} in {path}",)
    grounding = re.findall(
        r"Grounding table must record the ([a-z-]+) probe exactly once, got (\d+)",
        message,
    )
    if grounding:
        return tuple(
            f"ERROR: {PROBE_RULES.get(probe, 'grounding-probe-recorded')} "
            + f"Grounding table must record the {probe} probe exactly once, got "
            + f"{count} in {path}"
            for probe, count in grounding
        )
    if "gate_applicability.reason is required" in message:
        return (f"ERROR: {NOT_APPLICABLE_RULE} {message} in {path}",)
    return (f"ERROR: typed-document-invalid {message} in {path}",)


def _typed_frontmatter(
    frontmatter: Mapping[str, object],
    policy: _SpecFormatPolicy,
    path: Path,
    errors: list[str],
) -> tuple[Any, Any] | None:
    schema = _schema_module()
    gate = frontmatter.get("gate_applicability")
    if gate is None:
        gate = {
            "disposition": "red-required",
            "work_class": "behavior",
            "ui_surface": "non-browser",
        }
    if not isinstance(gate, Mapping):
        return None

    enum_values = (
        (
            "disposition",
            "gate_applicability_disposition",
            "gate-applicability-closed-class",
        ),
        ("work_class", "work_class", "gate-applicability-closed-class"),
        ("ui_surface", "ui_surface", "gate-applicability-closed-class"),
    )
    for key, enum_name, error_id in enum_values:
        value = gate.get(key)
        if value not in ENUMS[enum_name]:
            errors.append(
                f"ERROR: {error_id} gate_applicability.{key} '{value}' is "
                + f"not a recognized {key.replace('_', ' ')} in {path}"
            )
            return None

    try:
        gate_model = schema.GateApplicability(
            disposition=schema.GateApplicabilityDisposition(gate["disposition"]),
            work_class=schema.WorkClass(gate["work_class"]),
            ui_surface=schema.UiSurface(gate["ui_surface"]),
            reason=gate.get("reason"),
        )
        front_model = schema.MoldSpecFrontmatter(
            slug=frontmatter.get("slug", "legacy-spec"),
            status=frontmatter.get("status", "draft"),
            source=frontmatter.get("source", "legacy"),
            created=frontmatter.get("created", "unknown"),
            confidence=schema.SpecConfidence(frontmatter.get("confidence", "medium")),
            gate_applicability=gate_model,
            gates_overridden=frontmatter.get("gates_overridden", ()),
            agent_introduced_scope=frontmatter.get("agent_introduced_scope", ()),
            entity_referent_bindings=frontmatter.get("entity_referent_bindings", ()),
        )
    except (TypeError, ValueError) as error:
        errors.extend(_typed_errors(str(error), path))
        return None
    return schema, front_model


def _typed_test_rows(
    schema: Any, rows: list[list[str]], path: Path, errors: list[str]
) -> tuple[list[Any], bool]:
    typed: list[Any] = []
    had_error = False
    for row in rows:
        acceptance_id = row[_AC_ID_COL]
        mode = row[_MODE_COL]
        if mode not in ENUMS["mode"]:
            errors.append(
                f"ERROR: mode-closed-class Test Contracts row '{acceptance_id}' "
                + f"has unknown Mode '{mode}' in {path}"
            )
            had_error = True
            continue
        try:
            typed.append(
                schema.TestContractRow(
                    acceptance_id=acceptance_id,
                    interface_referent=row[1],
                    outermost_stable_seam=row[2],
                    expected_failure=row[3],
                    mode=schema.TestContractMode(mode),
                    interface_version=row[_INTERFACE_VERSION_COL],
                    matrix_rows=_matrix_rows(row[_MATRIX_ROWS_COL]),
                )
            )
        except (TypeError, ValueError) as error:
            errors.extend(_typed_errors(str(error), path))
            had_error = True
    return typed, had_error


def _typed_grounding_rows(
    schema: Any, rows: list[list[str]], path: Path, errors: list[str]
) -> tuple[list[Any], bool]:
    typed: list[Any] = []
    had_error = False
    for row in rows:
        probe = row[_PROBE_COL]
        outcome = row[_OUTCOME_COL]
        if probe not in ENUMS["grounding_probe"]:
            errors.append(
                "ERROR: grounding-probe-closed-class Grounding row has unknown "
                + f"Probe '{probe}' in {path}"
            )
            had_error = True
            continue
        if outcome not in ENUMS["grounding_outcome"]:
            errors.append(
                f"ERROR: grounding-outcome-closed-class Grounding row '{probe}' "
                + f"has unknown Outcome '{outcome}' in {path}"
            )
            had_error = True
            continue
        try:
            typed.append(
                schema.GroundingRow(
                    probe=schema.GroundingProbe(probe),
                    outcome=schema.GroundingOutcome(outcome),
                    evidence=row[_EVIDENCE_COL],
                )
            )
        except (TypeError, ValueError) as error:
            rule = PROBE_RULES[probe]
            message = str(error)
            if "evidence" in message:
                message = (
                    f"Grounding row '{probe}' records no evidence; an unavailable "
                    + "probe still records what was attempted"
                )
                errors.append(f"ERROR: {rule} {message} in {path}")
            else:
                errors.extend(_typed_errors(message, path))
            had_error = True
    return typed, had_error


def _validate_typed_document(
    frontmatter: Mapping[str, object],
    policy: _SpecFormatPolicy,
    acceptance_ids: list[str],
    test_rows: list[list[str]],
    grounding_rows: list[list[str]],
    grounding_present: bool,
    path: Path,
    errors: list[str],
) -> None:
    typed_frontmatter = _typed_frontmatter(frontmatter, policy, path, errors)
    if typed_frontmatter is None:
        return
    schema, front_model = typed_frontmatter
    typed_contracts, contract_errors = _typed_test_rows(schema, test_rows, path, errors)
    typed_grounding, grounding_errors = _typed_grounding_rows(
        schema, grounding_rows, path, errors
    )
    if not grounding_present and not policy.requires_section(
        "Grounding", default_required=True
    ):
        typed_grounding = [
            schema.GroundingRow(
                probe=probe,
                outcome=schema.GroundingOutcome.UNAVAILABLE,
                evidence="Grounding is not required by this Mold format policy",
            )
            for probe in schema.GroundingProbe
        ]
    if contract_errors or grounding_errors:
        return
    try:
        schema.MoldSpecDocument(
            frontmatter=front_model,
            acceptance_ids=tuple(acceptance_ids),
            test_contract_rows=tuple(typed_contracts),
            grounding_rows=tuple(typed_grounding),
        )
    except (TypeError, ValueError) as error:
        errors.extend(_typed_errors(str(error), path))


def validate(path: Path, *, strict: bool = False) -> tuple[list[str], str | None]:
    """Return Markdown-shape errors and an optional legacy-format notice."""
    errors: list[str] = []
    text = path.read_text(encoding="utf-8")
    frontmatter, body = _split_frontmatter(text)
    policy = spec_format_policy(frontmatter, strict=strict)
    found_sections, duplicate_headings = _find_sections(body)
    source = frontmatter.get("source")
    gate_applicability = frontmatter.get("gate_applicability")
    disposition = (
        gate_applicability.get("disposition")
        if isinstance(gate_applicability, Mapping)
        else None
    )

    if source is not None and not isinstance(source, str):
        errors.append(
            "ERROR: spec-provenance-invalid frontmatter source must be a scalar "
            + f"string in {path}"
        )
    if strict and not is_hardened_provenance(frontmatter):
        errors.append(
            "ERROR: spec-provenance-required frontmatter source must be a mold "
            + f"provenance marker when minting a spec in {path}"
        )

    for name in sorted(set(duplicate_headings)):
        errors.append(
            f"ERROR: duplicate-heading '## {name}' heading appears more than once "
            + f"in {path}"
        )

    section_requirements = [
        (section["name"], not section["optional"]) for section in SECTIONS
    ]
    section_requirements.append(("Contract", False))
    for name, default_required in section_requirements:
        required = policy.requires_section(name, default_required=default_required)
        if name == "Test Contracts" and disposition == "not-applicable":
            required = False
        if required and _canonical_heading(name) not in found_sections:
            errors.append(
                f"ERROR: missing-required-section '{name}' section not "
                + f"found in {path}"
            )

    test_contracts_lines = found_sections.get(_canonical_heading("Test Contracts"))
    test_rows: list[list[str]] = []
    if disposition == "not-applicable" and test_contracts_lines is not None:
        errors.append(
            f"ERROR: {NOT_APPLICABLE_RULE} gate_applicability.disposition="
            + f"not-applicable requires no Test Contracts section in {path}"
        )
    elif test_contracts_lines is not None:
        test_rows = _declared_table_rows(
            test_contracts_lines,
            TABLE_COLUMNS,
            "Test Contracts",
            "test-contracts-table-shape",
            path,
            errors,
        )

    grounding_lines = found_sections.get(_canonical_heading("Grounding"))
    grounding_rows: list[list[str]] = []
    if grounding_lines is not None:
        grounding_rows = _declared_table_rows(
            grounding_lines,
            GROUNDING_COLUMNS,
            "Grounding",
            "grounding-table-shape",
            path,
            errors,
        )

    acceptance_lines = found_sections.get(_canonical_heading("Acceptance"), [])
    acceptance_ids = (
        [] if disposition == "not-applicable" else _acceptance_ids(acceptance_lines)
    )

    if not isinstance(gate_applicability, Mapping):
        if "gate_applicability" in frontmatter or policy.requires_gate_applicability():
            errors.append(
                "ERROR: gate-applicability-required frontmatter gate_applicability is "
                + f"missing or unparseable in {path}"
            )

    _validate_typed_document(
        frontmatter,
        policy,
        acceptance_ids,
        test_rows,
        grounding_rows,
        grounding_lines is not None,
        path,
        errors,
    )
    return errors, policy.notice


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    _ = parser.add_argument(
        "spec_path", type=Path, help="Path to the mold spec markdown file."
    )
    _ = parser.add_argument(
        "--strict",
        action="store_true",
        help=(
            "Mint/rewrite posture: enforce the current hardened format "
            "unconditionally, with no legacy acceptance."
        ),
    )
    args = parser.parse_args(argv)
    spec_path = cast(Path, args.spec_path)
    strict = cast(bool, args.strict)

    if not spec_path.is_file():
        print(f"ERROR: spec not found: {spec_path}", file=sys.stderr)
        return 1

    errors, notice = validate(spec_path, strict=strict)
    if notice is not None:
        print(f"{notice} in {spec_path}")
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        print(f"\nFAIL: {len(errors)} error(s) in {spec_path}", file=sys.stderr)
        return 1

    print(f"OK: {spec_path} is a valid mold spec")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
