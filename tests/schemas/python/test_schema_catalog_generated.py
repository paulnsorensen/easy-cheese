"""Checks for the generated public schema catalog."""

from __future__ import annotations

import sys
from pathlib import Path
from types import ModuleType
from typing import cast

import pytest

from scripts import runtime_gates

REPO_ROOT = Path(__file__).resolve().parents[3]


def test_checked_in_generated_file_bytes_covers_missing_stale_and_matching(
    tmp_path: Path,
) -> None:
    generated = tmp_path / "_schema_catalog.py"
    validate = runtime_gates._checked_in_generated_file_bytes  # pyright: ignore[reportPrivateUsage]
    with pytest.raises(RuntimeError, match="is missing"):
        _ = validate("current", generated, artifact_name="schema catalog")
    _ = generated.write_bytes(b"stale")
    with pytest.raises(RuntimeError, match="is stale"):
        _ = validate("current", generated, artifact_name="schema catalog")
    _ = generated.write_bytes(b"current")
    assert validate("current", generated, artifact_name="schema catalog") == b"current"


def test_checked_in_catalog_matches_build_generator() -> None:
    catalog = REPO_ROOT / "src/easy_cheese_schemas/_schema_catalog.py"
    assert catalog.read_text(encoding="utf-8") == runtime_gates._compiled_schema_catalog_source()  # pyright: ignore[reportPrivateUsage]


def test_catalog_compilation_follows_inventory(monkeypatch: pytest.MonkeyPatch) -> None:
    stub = ModuleType("easy_cheese_schemas._fresh_plan_stub")
    fresh_plan = type("FreshPlan", (), {})
    stub.__dict__["registered_contracts"] = lambda: (("fresh-plan", fresh_plan),)
    monkeypatch.setitem(sys.modules, stub.__name__, stub)
    inventory = runtime_gates._contract_modules_inventory()  # pyright: ignore[reportPrivateUsage]
    listed = cast(tuple[str, ...], getattr(inventory, "CONTRACT_MODULES"))
    monkeypatch.setattr(inventory, "CONTRACT_MODULES", (*listed, stub.__name__))
    rendered = runtime_gates._compiled_schema_catalog_source()  # pyright: ignore[reportPrivateUsage]
    assert "curd-plan" in rendered
    assert "fresh-plan" in rendered


def test_runtime_gate_rejects_stale_checked_in_catalog(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    compiled = runtime_gates._compiled_schema_catalog_source()  # pyright: ignore[reportPrivateUsage]
    stale = tmp_path / "_schema_catalog.py"
    _ = stale.write_text(compiled.replace('/pr-plan"', '/stale-plan"', 1), encoding="utf-8")
    assert stale.read_text(encoding="utf-8") != compiled
    monkeypatch.setattr(
        runtime_gates,
        "GENERATED_RUNTIME_SOURCES",
        ((stale, "schema catalog", runtime_gates._compiled_schema_catalog_source),),  # pyright: ignore[reportPrivateUsage]
    )
    assert f"checked-in schema catalog is stale; regenerate {stale}" in runtime_gates.check()
