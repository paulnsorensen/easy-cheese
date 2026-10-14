"""The removed phase contract leaves only private handoff routing."""

from __future__ import annotations

from pathlib import Path

import fromargs
import pytest

from easy_cheese.shared.phase_routes import RouteError, validate_route
from easy_cheese.shared.write_handoff_artifact import write_artifact
from easy_cheese_schemas import REGISTERED_CONTRACT_SCHEMA_URIS, registered_contracts


def test_phase_contract_is_not_published() -> None:
    assert (
        "https://schemas.easy-cheese.dev/phase-contract"
        not in REGISTERED_CONTRACT_SCHEMA_URIS
    )
    assert "phase-contract" not in {slug for slug, _ in registered_contracts()}


def test_private_handoff_route_rejects_invalid_destination() -> None:
    with pytest.raises(RouteError, match="mold -> cure"):
        validate_route("mold", "cure", "https://schemas.easy-cheese.dev/curd-plan")


def test_private_handoff_route_accepts_active_destination() -> None:
    validate_route("cook", "press", "https://schemas.easy-cheese.dev/curd-result")


def test_writer_rejects_invalid_route_without_creating_directory(
    tmp_path: Path,
) -> None:
    with pytest.raises(fromargs.CliError, match="mold -> cure is not declared"):
        _ = write_artifact(
            slug="bad-route",
            status="ok",
            phase="mold",
            next_skill="cure",
            payload_schema_uri="https://schemas.easy-cheese.dev/curd-plan",
            artifact="",
            orientation="must not be written",
            body=None,
            root=tmp_path,
        )
    assert not (tmp_path / ".cheese").exists()


def test_writer_rejects_wrong_schema_before_creating_directories(
    tmp_path: Path,
) -> None:
    with pytest.raises(fromargs.CliError, match="payload schema .* not declared"):
        _ = write_artifact(
            slug="wrong-schema",
            status="ok",
            phase="mold",
            next_skill="cook",
            payload_schema_uri="urn:easy-cheese:schema:curd-plan:1.0",
            artifact="",
            orientation="must not be written",
            body=None,
            root=tmp_path,
        )
    assert not (tmp_path / ".cheese").exists()


def test_writer_rejects_missing_phase_before_creating_directories(
    tmp_path: Path,
) -> None:
    with pytest.raises(fromargs.CliError, match="--phase must be non-empty"):
        _ = write_artifact(
            slug="missing-phase",
            status="ok",
            phase="",
            next_skill="done",
            artifact="",
            orientation="must not be written",
            body=None,
            root=tmp_path,
        )
    assert not (tmp_path / ".cheese").exists()


def test_writer_rejects_unknown_phase_before_creating_directories(
    tmp_path: Path,
) -> None:
    with pytest.raises(fromargs.CliError, match="unknown source phase 'unknown'"):
        _ = write_artifact(
            slug="unknown-phase",
            status="ok",
            phase="unknown",
            next_skill="done",
            artifact="",
            orientation="must not be written",
            body=None,
            root=tmp_path,
        )
    assert not (tmp_path / ".cheese").exists()


def test_writer_never_follows_preplaced_predictable_tmp_symlink(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("EASY_CHEESE_HOME", str(tmp_path / "corpus"))
    monkeypatch.setenv("EASY_CHEESE_PROJECT", "route-removal-tests")
    target_dir = tmp_path / ".cheese" / "press"
    target_dir.mkdir(parents=True)
    sentinel = tmp_path / "sentinel"
    _ = sentinel.write_text("untouched", encoding="utf-8")
    predictable_tmp = target_dir / "safe.md.tmp"
    predictable_tmp.symlink_to(sentinel)
    _ = (tmp_path / "grounded.md").write_text("grounded context\n", encoding="utf-8")

    target = write_artifact(
        slug="safe",
        status="ok",
        phase="press",
        next_skill="age",
        artifact="",
        orientation="press completed",
        body=None,
        root=tmp_path,
        grounded=("grounded.md#1-1",),
    )

    assert target.exists()
    assert sentinel.read_text(encoding="utf-8") == "untouched"
    assert predictable_tmp.is_symlink()
