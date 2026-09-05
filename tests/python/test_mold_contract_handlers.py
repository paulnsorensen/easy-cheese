"""These tests cover the Mold contract adapter that `mold.pyz` dispatches.

The bundle tests in `test_mold_contract_publish.py` exercise the checked-in
archive. These tests exercise the adapter module directly, so a route change
fails here before the next bundle rebuild.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from easy_cheese.shared.publication import PublicationError
from easy_cheese.skills.mold import contract_handlers

CURD_PLAN_SCHEMA_URI = "https://schemas.easy-cheese.dev/curd-plan"


def _legacy_document(tmp_path: Path) -> Path:
    document = tmp_path / "legacy.json"
    _ = document.write_text(json.dumps({"kind": "curd_plan"}), encoding="utf-8")
    return document


def _migrate_argv(document: Path, tmp_path: Path, *extra: str) -> list[str]:
    return [
        str(document),
        "--source-schema-uri",
        CURD_PLAN_SCHEMA_URI,
        "--source-major",
        "0",
        "--source-minor",
        "13",
        "--operation-id",
        "op-phase",
        "--artifact-root",
        str(tmp_path / "artifacts"),
        *extra,
    ]


@pytest.mark.parametrize("option", ["--source-phase", "--destination-phase"])
def test_migrate_rejects_a_caller_selected_phase(
    tmp_path: Path, option: str
) -> None:
    """Mold owns its route. A caller cannot name either phase."""
    argv = _migrate_argv(_legacy_document(tmp_path), tmp_path, option, "cook")
    with pytest.raises(SystemExit) as exit_info:
        _ = contract_handlers.migrate_main(argv)
    assert exit_info.value.code == 2


def test_migrate_binds_the_mold_to_cook_route(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The adapter passes `mold` and `cook` to the shared migration helper."""
    seen: dict[str, object] = {}

    def _capture(_legacy: object, **kwargs: object) -> object:
        seen.update(kwargs)
        raise PublicationError("stop after the route is bound")

    monkeypatch.setattr(contract_handlers, "migrate", _capture)
    status = contract_handlers.migrate_main(
        _migrate_argv(_legacy_document(tmp_path), tmp_path)
    )
    assert status == 1
    assert seen["source_phase"] == "mold"
    assert seen["destination_phase"] == "cook"


def test_publish_binds_the_mold_to_cook_route(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The publish adapter names the same route and payload schema."""
    seen: dict[str, object] = {}

    def _capture(_document: object, _invocation: object, **kwargs: object) -> object:
        seen.update(kwargs)
        raise PublicationError("stop after the route is bound")

    monkeypatch.setattr(contract_handlers, "publish", _capture)
    document = tmp_path / "document.json"
    _ = document.write_text(json.dumps({"kind": "curd_plan"}), encoding="utf-8")
    invocation = tmp_path / "invocation.json"
    _ = invocation.write_text(json.dumps({"plan_id": "p-1"}), encoding="utf-8")
    status = contract_handlers.publish_main(
        [
            str(document),
            "--invocation",
            str(invocation),
            "--operation-id",
            "op-route",
            "--artifact-root",
            str(tmp_path / "artifacts"),
        ]
    )
    assert status == 1
    assert seen["source_phase"] == "mold"
    assert seen["destination_phase"] == "cook"
    assert seen["payload_schema_uri"] == CURD_PLAN_SCHEMA_URI
