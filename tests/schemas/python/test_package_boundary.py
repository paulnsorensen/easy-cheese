from __future__ import annotations

import ast
import importlib.util
from pathlib import Path

import easy_cheese_schemas


SCHEMA_ROOT = Path(easy_cheese_schemas.__file__).parent
RUNTIME_EXPORTS = frozenset(
    {"cook", "cure", "run_workflow", "resolve_artifact", "WriterCheckpoint", "BenchmarkReport"}
)
RELOCATED_MODULES = (
    "workflow",
    "artifacts",
    "benchmarks",
    "_phase_registry_compiler",
    "_schema_catalog_compiler",
    "_document_rules_compiler",
)


def test_schema_package_exposes_contracts_but_not_runtime_machinery() -> None:
    assert not RUNTIME_EXPORTS & set(vars(easy_cheese_schemas))
    for module in RELOCATED_MODULES:
        assert importlib.util.find_spec(f"easy_cheese_schemas.{module}") is None, module


def test_schema_sources_do_not_import_runtime_packages() -> None:
    forbidden_roots = ("easy_cheese", "milknado")
    for source in SCHEMA_ROOT.rglob("*.py"):
        tree = ast.parse(source.read_text(), filename=str(source))
        imported: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module is not None:
                imported.append(node.module)
        assert not any(
            name == root or name.startswith(f"{root}.")
            for name in imported
            for root in forbidden_roots
        ), f"{source} imports a runtime package: {imported}"
