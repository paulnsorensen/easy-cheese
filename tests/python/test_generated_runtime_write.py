"""The build writes the same generated runtime sources it checks."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
for _extra in (ROOT / "vendor", ROOT / "src", ROOT / "scripts"):
    if str(_extra) not in sys.path:
        sys.path.insert(0, str(_extra))

pytestmark = pytest.mark.skipif(  # noqa: V107
    importlib.util.find_spec("attrs") is None,
    reason="runtime requirements are not installed",
)

import build_pyz  # noqa: E402



def _schema_namespace() -> dict[str, object]:
    prefix = "easy_cheese_schemas."
    return {
        name: module
        for name, module in sys.modules.items()
        if name == "easy_cheese_schemas" or name.startswith(prefix)
    }
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


def test_schema_catalog_loader_uses_added_inventory_module(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An inventory-only module needs no build-driver special case."""
    schema_root = tmp_path / "easy_cheese_schemas"
    _ = schema_root.mkdir()
    for name in ("contracts", "pr_plan"):
        _ = (schema_root / f"{name}.py").write_bytes(
            (ROOT / "src" / "easy_cheese_schemas" / f"{name}.py").read_bytes()
        )
    _ = (schema_root / "transitive_helper.py").write_text(
        "VALUE = 'loaded'\n", encoding="utf-8"
    )
    extra_source = "\n".join(
        (
            "import easy_cheese_schemas.transitive_helper",
            "from easy_cheese_schemas.contracts import contract, marked_contracts_in",
            "import sys",
            "@contract('extra')",
            "class Extra: pass",
            "def registered_contracts():",
            "    return marked_contracts_in(sys.modules[__name__])",
            "",
        )
    )
    _ = (schema_root / "extra.py").write_text(extra_source, encoding="utf-8")
    before = _schema_namespace()
    monkeypatch.setattr(build_pyz, "SCHEMA_ROOT", schema_root)
    monkeypatch.setattr(
        build_pyz,
        "_schema_module_inventory",
        lambda: (
            "easy_cheese_schemas.contracts",
            "easy_cheese_schemas.pr_plan",
            "easy_cheese_schemas.extra",
        ),
    )

    source = build_pyz._compiled_schema_catalog_source()  # pyright: ignore[reportPrivateUsage]

    assert "EXTRA_SCHEMA_URI" in source
    assert _schema_namespace() == before


def test_schema_catalog_loader_restores_modules_after_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The isolated loader restores every shadowed module when execution fails."""
    schema_root = tmp_path / "easy_cheese_schemas"
    _ = schema_root.mkdir()
    for name in ("contracts", "pr_plan"):
        _ = (schema_root / f"{name}.py").write_bytes(
            (ROOT / "src" / "easy_cheese_schemas" / f"{name}.py").read_bytes()
        )
    _ = (schema_root / "transitive_helper.py").write_text(
        "VALUE = 'loaded'\n", encoding="utf-8"
    )
    extra_source = "\n".join(
        (
            "import easy_cheese_schemas.transitive_helper",
            "from easy_cheese_schemas.contracts import marked_contracts_in",
            "import sys",
            "def registered_contracts():",
            "    return marked_contracts_in(sys.modules[__name__])",
            "",
        )
    )
    _ = (schema_root / "extra.py").write_text(extra_source, encoding="utf-8")
    module_names = (
        "easy_cheese_schemas.contracts",
        "easy_cheese_schemas.pr_plan",
        "easy_cheese_schemas.extra",
        "easy_cheese_schemas.missing",
    )
    before = _schema_namespace()
    monkeypatch.setattr(build_pyz, "SCHEMA_ROOT", schema_root)
    monkeypatch.setattr(build_pyz, "_schema_module_inventory", lambda: module_names)

    with pytest.raises(FileNotFoundError):
        _ = build_pyz._compiled_schema_catalog_source()  # pyright: ignore[reportPrivateUsage]

    assert _schema_namespace() == before


def test_write_generated_command_reports_success(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The command exits successfully and builds no archive."""
    assert build_pyz.main(["build_pyz.py", "--write-generated"]) == 0
    assert "built " not in capsys.readouterr().out
