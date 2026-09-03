#!/usr/bin/env python3
"""Curdle-time SAP-posture validator for mold-produced specs.

Lenient acceptance (nothing is rewritten): heading case, heading trailing
punctuation, table cell whitespace, and fence dialect (``` vs ~~~) do not
affect validation; fenced code blocks are invisible to heading and table
detection regardless of dialect.

Strict semantic rejection: every mandatory section present with no duplicate
tracked heading; Test Contracts table has the seven declared columns and a
'---' delimiter row, and every row matches the column count; every
Acceptance ID appears exactly once in the table and vice versa; Mode is
drawn from its closed enum set; tracer rows leave Interface version/Matrix
rows blank; contract-matrix rows require both; the Grounding table records
each declared probe exactly once with a closed-set outcome and non-empty
evidence — an unavailable probe still leaves evidence rather than being
assumed; frontmatter gate_applicability must be present and parseable, with
disposition/work_class/ui_surface drawn from their closed enum sets;
not-applicable requires a reason and zero Test Contracts rows.

Legacy acceptance: the default (read) posture accepts v0.13-era specs — those
without a Mold provenance marker — indefinitely, waiving only the two parts the
hardened format added after v0.13 (the Test Contracts section and the
gate_applicability block) and printing a one-line NOTICE. ``--strict`` is the
mint/rewrite posture: the hardened format unconditionally, plus the provenance
marker itself. The policy lives once in ``easy_cheese_schemas.spec_format`` so
every release channel inherits it.

Rules are consumed from the generated, dependency-free ``_document_rules``
projection (built from the ``@document_contract("mold-spec")`` models in
contracts.py) so the rule data never drags the attrs-based model stack in.

ERROR:-line accumulation and exit codes follow .github/scripts/validate_wiki.py.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import TypedDict, cast

from easy_cheese.shared.document_rules import DOCUMENT_RULES
from easy_cheese_schemas.spec_format import is_hardened_provenance, spec_format_policy


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

_CROSS_FIELD_RULE_IDS: set[str] = {rule["rule_id"] for rule in RULES["cross_field_rules"]}


def _rule_id(rule_id: str) -> str:
    assert rule_id in _CROSS_FIELD_RULE_IDS, f"undeclared cross-field rule id: {rule_id}"
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
DELIMITER_CELL_RE = re.compile(r"^:?-+:?$")


def _canonical_heading(raw: str) -> str:
    """Lenient heading match: case-insensitive, trailing punctuation stripped."""
    return raw.strip().rstrip(".,;:!?").strip().lower()


def _split_frontmatter(text: str) -> tuple[dict[str, str | dict[str, str]], str]:
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


def _parse_yaml_block(lines: list[str]) -> dict[str, str | dict[str, str]]:
    """Minimal key: value / nested-mapping parser for mold frontmatter."""
    data: dict[str, str | dict[str, str]] = {}
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
            data[key] = value.strip('"').strip("'")
            i += 1
            continue
        nested: dict[str, str] = {}
        j = i + 1
        while j < len(lines) and (lines[j].startswith("  ") or not lines[j].strip()):
            nested_line = lines[j].strip()
            if nested_line and ":" in nested_line and not nested_line.startswith("-"):
                nk, _, nv = nested_line.partition(":")
                nested[nk.strip()] = nv.strip().strip('"').strip("'")
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
        errors.append(f"ERROR: {error_id} no table found in {section} section of {path}")
        return []
    header = parsed[0]
    if tuple(header) != columns:
        errors.append(
            f"ERROR: {error_id} {section} table columns {header} do not match the "
            + f"required columns {list(columns)} in {path}"
        )
        return []
    delimiter_row = parsed[1]
    if not delimiter_row or not all(DELIMITER_CELL_RE.match(cell) for cell in delimiter_row):
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


def _grounding_errors(rows: list[list[str]], path: Path) -> list[str]:
    """Every declared probe is recorded exactly once with non-empty evidence.

    An ``unavailable`` outcome is an accepted degrade path, but it still has to
    name what was attempted — the probe may be skipped, never assumed.
    """
    errors: list[str] = []
    recorded: dict[str, int] = {}
    for row in rows:
        probe = row[_PROBE_COL]
        outcome = row[_OUTCOME_COL]
        evidence = row[_EVIDENCE_COL]
        if probe not in ENUMS["grounding_probe"]:
            errors.append(
                "ERROR: grounding-probe-closed-class Grounding row has unknown "
                + f"Probe '{probe}' in {path}"
            )
            continue
        recorded[probe] = recorded.get(probe, 0) + 1
        if outcome not in ENUMS["grounding_outcome"]:
            errors.append(
                f"ERROR: grounding-outcome-closed-class Grounding row '{probe}' has "
                + f"unknown Outcome '{outcome}' in {path}"
            )
        if not evidence:
            errors.append(
                f"ERROR: {PROBE_RULES[probe]} Grounding row '{probe}' records no "
                + "evidence; an unavailable probe still records what was attempted "
                + f"in {path}"
            )
    for probe, rule in PROBE_RULES.items():
        count = recorded.get(probe, 0)
        if count == 0:
            errors.append(
                f"ERROR: {rule} the Grounding table does not record the '{probe}' "
                + f"probe in {path}"
            )
        elif count > 1:
            errors.append(
                f"ERROR: {rule} the Grounding table records the '{probe}' probe "
                + f"{count} times in {path}"
            )
    return errors


def _acceptance_ids(content_lines: list[str]) -> list[str]:
    ids: list[str] = []
    for line in content_lines:
        match = ACCEPTANCE_ID_RE.match(line.strip())
        if match:
            ids.append(match.group(1))
    return ids


def validate(path: Path, *, strict: bool = False) -> tuple[list[str], str | None]:
    """Return accumulated ``ERROR:`` lines plus a legacy NOTICE when one applies."""
    errors: list[str] = []
    text = path.read_text(encoding="utf-8")
    frontmatter, body = _split_frontmatter(text)
    policy = spec_format_policy(frontmatter, strict=strict)
    found_sections, duplicate_headings = _find_sections(body)
    source = frontmatter.get("source")
    gate_applicability = frontmatter.get("gate_applicability")
    disposition = (
        gate_applicability.get("disposition")
        if isinstance(gate_applicability, dict)
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
        if not required:
            continue
        canonical = _canonical_heading(name)
        if canonical not in found_sections:
            errors.append(
                f"ERROR: missing-required-section '{name}' section not "
                + f"found in {path}"
            )

    test_contracts_lines = found_sections.get(_canonical_heading("Test Contracts"))
    rows: list[list[str]] = []
    if disposition == "not-applicable" and test_contracts_lines is not None:
        errors.append(
            f"ERROR: {NOT_APPLICABLE_RULE} gate_applicability.disposition="
            + f"not-applicable requires no Test Contracts section in {path}"
        )
    elif test_contracts_lines is not None:
        rows = _declared_table_rows(
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
    if grounding_lines is not None or policy.requires_section(
        "Grounding", default_required=True
    ):
        errors.extend(_grounding_errors(grounding_rows, path))

    acceptance_lines = found_sections.get(_canonical_heading("Acceptance"), [])
    declared_ids = (
        [] if disposition == "not-applicable" else _acceptance_ids(acceptance_lines)
    )

    counts: dict[str, int] = {}
    for row in rows:
        acceptance_id = row[_AC_ID_COL]
        counts[acceptance_id] = counts.get(acceptance_id, 0) + 1

    for acceptance_id in declared_ids:
        count = counts.get(acceptance_id, 0)
        if count == 0:
            errors.append(
                f"ERROR: {AC_COVERAGE_RULE} acceptance ID '{acceptance_id}' is "
                + f"absent from the Test Contracts table in {path}"
            )
        elif count > 1:
            errors.append(
                f"ERROR: {AC_COVERAGE_RULE} acceptance ID '{acceptance_id}' "
                + f"appears {count} times in the Test Contracts table in {path}"
            )
    for acceptance_id in sorted(set(counts) - set(declared_ids)):
        errors.append(
            f"ERROR: {AC_COVERAGE_RULE} acceptance ID '{acceptance_id}' appears "
            + f"in the Test Contracts table but is not declared in Acceptance in {path}"
        )

    for row in rows:
        acceptance_id = row[_AC_ID_COL]
        mode = row[_MODE_COL]
        interface_version = row[_INTERFACE_VERSION_COL]
        matrix_rows = row[_MATRIX_ROWS_COL]
        if mode not in ENUMS["mode"]:
            errors.append(
                f"ERROR: mode-closed-class Test Contracts row '{acceptance_id}' has "
                + f"unknown Mode '{mode}' in {path}"
            )
            continue
        if mode == "tracer":
            if interface_version or matrix_rows:
                errors.append(
                    f"ERROR: {TRACER_ROW_RULE} Test Contracts row "
                    + f"'{acceptance_id}' is tracer mode and must leave Interface "
                    + f"version and Matrix rows blank in {path}"
                )
        elif mode == "contract-matrix":
            if not interface_version or not matrix_rows:
                errors.append(
                    f"ERROR: {CONTRACT_MATRIX_ROW_RULE} Test Contracts row "
                    + f"'{acceptance_id}' is contract-matrix mode and requires both "
                    + f"Interface version and Matrix rows in {path}"
                )

    if not isinstance(gate_applicability, dict):
        if "gate_applicability" in frontmatter or policy.requires_gate_applicability():
            errors.append(
                "ERROR: gate-applicability-required frontmatter gate_applicability is "
                + f"missing or unparseable in {path}"
            )
    else:
        disposition = gate_applicability.get("disposition")
        work_class = gate_applicability.get("work_class")
        ui_surface = gate_applicability.get("ui_surface")
        reason = gate_applicability.get("reason")
        if disposition not in ENUMS["gate_applicability_disposition"]:
            errors.append(
                "ERROR: gate-applicability-closed-class gate_applicability.disposition "
                + f"'{disposition}' is not a recognized disposition in {path}"
            )
        if work_class not in ENUMS["work_class"]:
            errors.append(
                "ERROR: gate-applicability-closed-class gate_applicability.work_class "
                + f"'{work_class}' is not a recognized work class in {path}"
            )
        if ui_surface not in ENUMS["ui_surface"]:
            errors.append(
                "ERROR: gate-applicability-closed-class gate_applicability.ui_surface "
                + f"'{ui_surface}' is not a recognized UI surface in {path}"
            )
        if disposition == "not-applicable":
            if not reason:
                errors.append(
                    f"ERROR: {NOT_APPLICABLE_RULE} gate_applicability.reason is "
                    + f"required when disposition is not-applicable in {path}"
                )


    return errors, policy.notice


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    _ = parser.add_argument("spec_path", type=Path, help="Path to the mold spec markdown file.")
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
