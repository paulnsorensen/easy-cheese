from __future__ import annotations

import ast
import importlib.util
from pathlib import Path

import easy_cheese_schemas


SCHEMA_ROOT = Path(easy_cheese_schemas.__file__).parent


def test_schema_package_exposes_contracts_but_not_runtime_machinery() -> None:
    assert not hasattr(easy_cheese_schemas, "cook")
    assert not hasattr(easy_cheese_schemas, "cure")
    assert not hasattr(easy_cheese_schemas, "run_workflow")
    assert not hasattr(easy_cheese_schemas, "resolve_artifact")
    assert not hasattr(easy_cheese_schemas, "WriterCheckpoint")
    assert not hasattr(easy_cheese_schemas, "BenchmarkReport")
    assert importlib.util.find_spec("easy_cheese_schemas.workflow") is None
    assert importlib.util.find_spec("easy_cheese_schemas.artifacts") is None
    assert importlib.util.find_spec("easy_cheese_schemas.benchmarks") is None
    assert importlib.util.find_spec("easy_cheese_schemas._phase_registry_compiler") is None
    assert importlib.util.find_spec("easy_cheese_schemas._schema_catalog_compiler") is None
    assert importlib.util.find_spec("easy_cheese_schemas._document_rules_compiler") is None


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


def test_runtime_machinery_lives_in_shared_package() -> None:
    import easy_cheese.shared.artifacts as artifacts
    import easy_cheese.shared.workflow as workflow

    assert artifacts.__file__ is not None
    assert workflow.__file__ is not None
    assert Path(artifacts.__file__).parent == Path(workflow.__file__).parent
    assert Path(artifacts.__file__).parent == SCHEMA_ROOT.parent / "easy_cheese" / "shared"
