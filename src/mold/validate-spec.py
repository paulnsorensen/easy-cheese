#!/usr/bin/env python3
"""Curdle-time SAP-posture validator for mold-produced specs.

Lenient syntax repair (never inventing meaning): heading case, heading
trailing punctuation, table cell whitespace, fence dialect (``` vs ~~~).
Strict semantic rejection: every mandatory section present; Test Contracts
table has the seven declared columns; every Acceptance ID appears exactly
once in the table and vice versa; tracer rows leave Interface
version/Matrix rows blank; contract-matrix rows require both; gate
applicability coherence (not-applicable needs a reason and zero contract
rows, red-required needs at least one).

Rules are consumed from the generated, dependency-free ``_document_rules``
projection (built from the ``@document_contract("mold-spec")`` models in
contracts.py) so mold.pyz stays free of the attrs-based schema stack.

ERROR:-line accumulation and exit codes follow .github/scripts/validate_wiki.py.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _document_rules import DOCUMENT_RULES  # noqa: E402

RULES = DOCUMENT_RULES["mold-spec"]
SECTIONS = RULES["sections"]
_TEST_CONTRACTS_SECTION = next(s for s in SECTIONS if s["name"] == "Test Contracts")
TABLE_COLUMNS: tuple[str, ...] = tuple(_TEST_CONTRACTS_SECTION["table"]["columns"])

HEADING_RE = re.compile(r"^##(?!#)\s+(.+?)\s*$")
ACCEPTANCE_ID_RE = re.compile(r"^-\s*(AC-\d+)\s*:")


def _canonical_heading(raw: str) -> str:
    """Lenient heading match: case-insensitive, trailing punctuation stripped."""
    return raw.strip().rstrip(".,;:!?").strip().lower()


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


def _parse_yaml_block(lines: list[str]) -> dict[str, object]:
    """Minimal key: value / nested-mapping parser for mold frontmatter."""
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


def _find_sections(body: str) -> dict[str, list[str]]:
    """Map canonical heading name -> section content lines (lenient heading match)."""
    lines = body.splitlines()
    headings: list[tuple[int, str]] = []
    for lineno, line in enumerate(lines):
        match = HEADING_RE.match(line)
        if match:
            headings.append((lineno, _canonical_heading(match.group(1))))
    found: dict[str, list[str]] = {}
    for idx, (lineno, name) in enumerate(headings):
        end = headings[idx + 1][0] if idx + 1 < len(headings) else len(lines)
        found[name] = lines[lineno + 1 : end]
    return found


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


def _acceptance_ids(content_lines: list[str]) -> list[str]:
    ids: list[str] = []
    for line in content_lines:
        match = ACCEPTANCE_ID_RE.match(line.strip())
        if match:
            ids.append(match.group(1))
    return ids


def validate(path: Path) -> list[str]:
    errors: list[str] = []
    text = path.read_text(encoding="utf-8")
    frontmatter, body = _split_frontmatter(text)
    found_sections = _find_sections(body)

    for section in SECTIONS:
        if section["optional"]:
            continue
        canonical = _canonical_heading(section["name"])
        if canonical not in found_sections:
            errors.append(
                f"ERROR: missing-required-section '{section['name']}' section not "
                f"found in {path}"
            )

    test_contracts_lines = found_sections.get(_canonical_heading("Test Contracts"))
    rows: list[list[str]] = []
    if test_contracts_lines is not None:
        parsed = _parse_table(test_contracts_lines)
        if parsed is None:
            errors.append(
                f"ERROR: test-contracts-table-shape no table found in Test "
                f"Contracts section of {path}"
            )
        else:
            header, data_rows = parsed[0], parsed[2:] if len(parsed) > 1 else []
            if tuple(header) != TABLE_COLUMNS:
                errors.append(
                    f"ERROR: test-contracts-table-shape Test Contracts table columns "
                    f"{header} do not match the required seven columns {list(TABLE_COLUMNS)} "
                    f"in {path}"
                )
            else:
                rows = [row for row in data_rows if len(row) == len(TABLE_COLUMNS)]

    acceptance_lines = found_sections.get(_canonical_heading("Acceptance"), [])
    declared_ids = _acceptance_ids(acceptance_lines)

    counts: dict[str, int] = {}
    for row in rows:
        acceptance_id = row[0]
        counts[acceptance_id] = counts.get(acceptance_id, 0) + 1

    for acceptance_id in declared_ids:
        count = counts.get(acceptance_id, 0)
        if count == 0:
            errors.append(
                f"ERROR: ac-coverage-exactly-once acceptance ID '{acceptance_id}' is "
                f"absent from the Test Contracts table in {path}"
            )
        elif count > 1:
            errors.append(
                f"ERROR: ac-coverage-exactly-once acceptance ID '{acceptance_id}' "
                f"appears {count} times in the Test Contracts table in {path}"
            )
    for acceptance_id in sorted(set(counts) - set(declared_ids)):
        errors.append(
            f"ERROR: ac-coverage-exactly-once acceptance ID '{acceptance_id}' appears "
            f"in the Test Contracts table but is not declared in Acceptance in {path}"
        )

    for row in rows:
        acceptance_id, mode, interface_version, matrix_rows = row[0], row[4], row[5], row[6]
        if mode == "tracer":
            if interface_version or matrix_rows:
                errors.append(
                    f"ERROR: tracer-row-blank-matrix-cells Test Contracts row "
                    f"'{acceptance_id}' is tracer mode and must leave Interface "
                    f"version and Matrix rows blank in {path}"
                )
        elif mode == "contract-matrix":
            if not interface_version or not matrix_rows:
                errors.append(
                    f"ERROR: contract-matrix-row-requires-both Test Contracts row "
                    f"'{acceptance_id}' is contract-matrix mode and requires both "
                    f"Interface version and Matrix rows in {path}"
                )

    gate_applicability = frontmatter.get("gate_applicability")
    if isinstance(gate_applicability, dict):
        disposition = gate_applicability.get("disposition")
        reason = gate_applicability.get("reason")
        if disposition == "not-applicable":
            if not reason:
                errors.append(
                    f"ERROR: not-applicable-closed-class gate_applicability.reason is "
                    f"required when disposition is not-applicable in {path}"
                )
            if rows:
                errors.append(
                    f"ERROR: not-applicable-closed-class gate_applicability.disposition="
                    f"not-applicable requires zero Test Contracts rows in {path}"
                )
        elif disposition == "red-required" and not rows:
            errors.append(
                f"ERROR: gate-applicability-red-required-needs-contracts "
                f"gate_applicability.disposition=red-required requires at least one "
                f"Test Contracts row in {path}"
            )

    return errors


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("spec_path", type=Path, help="Path to the mold spec markdown file.")
    args = parser.parse_args(argv)

    if not args.spec_path.is_file():
        print(f"ERROR: spec not found: {args.spec_path}", file=sys.stderr)
        return 1

    errors = validate(args.spec_path)
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        print(f"\nFAIL: {len(errors)} error(s) in {args.spec_path}", file=sys.stderr)
        return 1

    print(f"OK: {args.spec_path} is a valid mold spec")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
