"""curd-ssfe-1: MoldSpecDocument section coverage and compiler determinism."""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMAS_ROOT = REPO_ROOT / "src" / "easy_cheese_schemas"
GENERATED = REPO_ROOT / "src" / "easy_cheese" / "shared" / "document_rules.py"
CURDLE_MD = REPO_ROOT / "skills" / "mold" / "references" / "curdle.md"

if str(SCHEMAS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCHEMAS_ROOT))

import contracts  # noqa: E402
import _document_rules_compiler as compiler  # noqa: E402

_OPTIONAL_SECTIONS = {"Deferred follow-ups", "Reproduction", "References"}


def _curdle_template_section_headings() -> list[str]:
    text = CURDLE_MD.read_text(encoding="utf-8")
    start = text.index("## Spec template\n")
    end = text.index("\n## Issue template\n", start)
    section = text[start:end]
    open_match = re.search(r"```markdown\n", section)
    assert open_match, "curdle.md must contain a fenced Spec template block"
    close_index = section.rindex("\n```")
    template = section[open_match.end():close_index]
    headings = []
    for line in template.splitlines():
        if line.startswith("## "):
            name = line[3:].strip()
            name = re.sub(r"\s*\(.*\)$", "", name)
            headings.append(name)
    return headings


def test_mold_spec_document_declares_full_curdle_template_section_set() -> None:
    declared = [section.name for section in contracts.MoldSpecDocument.sections]
    assert declared == _curdle_template_section_headings()

    optional = {
        section.name for section in contracts.MoldSpecDocument.sections if section.optional
    }
    assert optional == _OPTIONAL_SECTIONS


def test_mold_spec_document_declares_seven_column_test_contracts_table() -> None:
    sections = {section.name: section for section in contracts.MoldSpecDocument.sections}
    table = sections["Test Contracts"].table
    assert table is not None
    assert table.columns == (
        "Acceptance ID",
        "Interface referent",
        "Outermost stable seam",
        "Expected failure",
        "Mode",
        "Interface version",
        "Matrix rows",
    )
    assert table.per_row


def test_mold_spec_document_declares_cross_field_rules() -> None:
    rule_ids = {rule.rule_id for rule in contracts.MoldSpecDocument.cross_field_rules}
    assert rule_ids == {
        "ac-coverage-exactly-once",
        "tracer-row-blank-matrix-cells",
        "contract-matrix-row-requires-both",
        "not-applicable-closed-class",
    }


def test_ac_coverage_validator_rejects_missing_and_duplicate_ids() -> None:
    frontmatter = contracts.MoldSpecFrontmatter(
        slug="example-spec",
        status="draft",
        source="mold-handshake",
        created="2026-08-23",
        confidence=contracts.SpecConfidence.HIGH,
        gate_applicability=contracts.GateApplicability(
            disposition=contracts.GateApplicabilityDisposition.RED_REQUIRED,
            work_class=contracts.WorkClass.BEHAVIOR,
            ui_surface=contracts.UiSurface.NON_BROWSER,
        ),
    )
    row = contracts.TestContractRow(
        acceptance_id="AC-1",
        interface_referent="thing",
        outermost_stable_seam="seam",
        expected_failure="witness",
        mode=contracts.TestContractMode.TRACER,
    )
    contracts.MoldSpecDocument(
        frontmatter=frontmatter, acceptance_ids=("AC-1",), test_contract_rows=(row,)
    )

    with pytest.raises(ValueError, match="AC-2"):
        contracts.MoldSpecDocument(
            frontmatter=frontmatter,
            acceptance_ids=("AC-1", "AC-2"),
            test_contract_rows=(row,),
        )


def test_document_rules_compiler_render_rejects_duplicate_slugs() -> None:
    with pytest.raises(ValueError, match="duplicate slugs"):
        compiler.render(
            [("mold-spec", contracts.MoldSpecDocument), ("mold-spec", contracts.MoldSpecDocument)]
        )


def test_document_rules_compiler_is_deterministic_and_matches_checked_in_file() -> None:
    pairs = compiler.collect(contracts)
    first = compiler.render(pairs)
    second = compiler.render(compiler.collect(contracts))
    assert first == second
    assert first == GENERATED.read_text(encoding="utf-8")


def test_generated_document_rules_module_imports_only_stdlib_names() -> None:
    source = GENERATED.read_text(encoding="utf-8")
    tree = ast.parse(source)
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                names.add(node.module.split(".")[0])
    assert names == {"__future__"}
    assert names <= set(sys.stdlib_module_names)

    namespace: dict[str, object] = {}
    exec(compile(source, str(GENERATED), "exec"), namespace)
    rules = namespace["DOCUMENT_RULES"]["mold-spec"]
    assert {section["name"] for section in rules["sections"]} == set(
        _curdle_template_section_headings()
    )
    assert {rule["rule_id"] for rule in rules["cross_field_rules"]} == {
        "ac-coverage-exactly-once",
        "tracer-row-blank-matrix-cells",
        "contract-matrix-row-requires-both",
        "not-applicable-closed-class",
    }
    assert set(rules["enums"]) == {
        "mode",
        "gate_applicability_disposition",
        "work_class",
        "ui_surface",
    }


def test_generated_document_rules_module_has_no_wrapped_string_fragments() -> None:
    """Regression for the implicit-string-concatenation CodeQL alerts: pprint
    must not wrap a string literal across lines (quote-then-newline-then-quote)."""
    lines = GENERATED.read_text(encoding="utf-8").splitlines()
    non_blank = [line for line in lines if line.strip()]
    for current, following in zip(non_blank, non_blank[1:]):
        assert not (current.rstrip().endswith("'") and following.strip().startswith("'")), (
            f"wrapped string fragment: {current!r} -> {following!r}"
        )
