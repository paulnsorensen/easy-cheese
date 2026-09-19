"""The build writes the same generated runtime sources it checks."""

from __future__ import annotations

import importlib
import importlib.util
import shutil
import subprocess
import sys
from pathlib import Path
from typing import cast

import pytest

ROOT = Path(__file__).resolve().parents[2]
for _extra in (ROOT / "vendor", ROOT / "src", ROOT / "scripts"):
    if str(_extra) not in sys.path:
        sys.path.insert(0, str(_extra))

pytestmark = pytest.mark.skipif(  # noqa: V107
    importlib.util.find_spec("attrs") is None,
    reason="runtime requirements are not installed",
)

import attrs  # noqa: E402

import build_pyz  # noqa: E402
from easy_cheese_schemas import schema_runtime  # noqa: E402
from easy_cheese_schemas._contract_modules import (  # noqa: E402
    CONTRACT_MODULES,
    DOCUMENT_RULES_TARGET,
)
from easy_cheese_schemas.contracts import marked_contracts_in  # noqa: E402
from easy_cheese_schemas.pr_plan import PrPlan  # noqa: E402


def test_write_generated_runtime_leaves_current_sources_unchanged() -> None:
    """A repository whose generated sources are current needs no write."""
    build_pyz._validate_generated_runtime()  # pyright: ignore[reportPrivateUsage]

    assert build_pyz.write_generated_runtime() == []


def test_write_generated_runtime_restores_a_stale_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The writer produces exactly what the staleness check demands."""
    source, artifact_name, render = build_pyz.GENERATED_RUNTIME_SOURCES[0]
    stale = tmp_path / source.name
    _ = stale.write_bytes(b"# stale\n")
    monkeypatch.setattr(
        build_pyz, "GENERATED_RUNTIME_SOURCES", ((stale, artifact_name, render),)
    )

    with pytest.raises(RuntimeError, match=r"is stale"):
        build_pyz._validate_generated_runtime()  # pyright: ignore[reportPrivateUsage]

    assert build_pyz.write_generated_runtime() == [stale]
    assert stale.read_bytes() == source.read_bytes()
    build_pyz._validate_generated_runtime()  # pyright: ignore[reportPrivateUsage]


def test_stale_catalog_raises_on_first_use_not_import(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Import survives a stale catalog. The first catalog use raises."""
    real = schema_runtime.REGISTERED_CONTRACT_SCHEMA_URIS
    smaller = frozenset(uri for uri in real if uri != next(iter(real)))
    assert len(smaller) < len(real)
    monkeypatch.setattr(schema_runtime, "REGISTERED_CONTRACT_SCHEMA_URIS", smaller)
    schema_runtime._checked_registered_contracts.cache_clear()  # pyright: ignore[reportPrivateUsage]
    try:
        with pytest.raises(RuntimeError, match="catalog is stale"):
            _ = schema_runtime.supported_version_for(PrPlan)
    finally:
        schema_runtime._checked_registered_contracts.cache_clear()  # pyright: ignore[reportPrivateUsage]


def test_contract_module_inventory_resolves() -> None:
    """Every inventoried contract module carries marked contracts and imports."""
    for module_name in CONTRACT_MODULES:
        module = importlib.import_module(module_name)
        assert marked_contracts_in(module)

    document_module_name, attribute_name = DOCUMENT_RULES_TARGET
    document_module = importlib.import_module(document_module_name)
    target = cast(type, getattr(document_module, attribute_name))
    assert attrs.has(target)


def test_write_generated_command_reports_success(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The command exits successfully and builds no archive."""
    assert build_pyz.main(["build_pyz.py", "--write-generated"]) == 0
    assert "built " not in capsys.readouterr().out


def test_stale_catalog_on_disk_survives_import_and_write_generated_repairs_it(
    tmp_path: Path,
) -> None:
    """A stale checked-in catalog does not break package import.

    The staleness check runs on first catalog use. `--write-generated` can
    therefore import the package and rewrite the catalog it repairs. The
    probe runs in a subprocess so the stale copy is the one the import sees.
    """
    staged_src = tmp_path / "src"
    _ = shutil.copytree(ROOT / "src" / "easy_cheese_schemas", staged_src / "easy_cheese_schemas")
    catalog = staged_src / "easy_cheese_schemas" / "_schema_catalog.py"
    current = catalog.read_text(encoding="utf-8")
    stale = current.replace("        PR_PLAN_SCHEMA_URI,\n", "", 1)
    assert stale != current
    _ = catalog.write_text(stale, encoding="utf-8")
    probe = "\n".join(
        [
            "import sys",
            "from pathlib import Path",
            "staged_src, scripts, vendor, catalog = (Path(p) for p in sys.argv[1:5])",
            "sys.path[:0] = [str(staged_src), str(scripts), str(vendor)]",
            "import easy_cheese_schemas",
            "from easy_cheese_schemas import PrPlan, supported_version_for",
            "try:",
            "    supported_version_for(PrPlan)",
            "except RuntimeError as exc:",
            "    assert 'catalog is stale' in str(exc), exc",
            "else:",
            "    raise SystemExit('lazy check did not fire')",
            "import build_pyz",
            "build_pyz.GENERATED_RUNTIME_SOURCES = (",
            "    (catalog, 'schema catalog', build_pyz._compiled_schema_catalog_source),",
            ")",
            "changed = build_pyz.write_generated_runtime()",
            "assert changed == [catalog], changed",
            "print('repaired')",
        ]
    )
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            probe,
            str(staged_src),
            str(ROOT / "scripts"),
            str(ROOT / "vendor"),
            str(catalog),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "repaired"
    assert catalog.read_text(encoding="utf-8") == current
