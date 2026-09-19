"""Focused regressions for Cook ingress classification."""
from __future__ import annotations

from pathlib import Path

import pytest

from easy_cheese_schemas.mold_cook import MoldCookInputKind
from easy_cheese.skills.cook.preparation import CookInputError, classify_input


def test_explicit_mode_wins_and_rejects_a_declared_pointer(tmp_path: Path) -> None:
    pointer = tmp_path / "misleading.md"
    _ = pointer.write_text('{"operation_id": "stored"}', encoding="utf-8")

    with pytest.raises(CookInputError, match="declares canonical_pointer"):
        _ = classify_input(pointer, explicit_kind=MoldCookInputKind.TASK)


def test_declared_pointer_is_classified_before_filename_suffix(tmp_path: Path) -> None:
    pointer = tmp_path / "pointer.txt"
    _ = pointer.write_text('{"operation_id": "stored"}', encoding="utf-8")

    classified = classify_input(pointer)

    assert classified.kind is MoldCookInputKind.CANONICAL_POINTER
    assert classified.path == pointer
    assert classified.declared_kind is MoldCookInputKind.CANONICAL_POINTER


def test_declared_projection_is_not_downgraded_to_task_text(tmp_path: Path) -> None:
    continuation = tmp_path / "notes.txt"
    _ = continuation.write_text('{"status": "GATED"}', encoding="utf-8")

    classified = classify_input(continuation)

    assert classified.kind is MoldCookInputKind.CONTINUATION
    assert classified.kind is not MoldCookInputKind.TASK


def test_unrecognised_existing_artifact_fails_closed(tmp_path: Path) -> None:
    artifact = tmp_path / "result.bin"
    _ = artifact.write_bytes(b"not a Cook task")

    with pytest.raises(CookInputError, match="unrecognised artifact"):
        _ = classify_input(artifact)


def test_markdown_and_slug_inputs_keep_their_supported_routes(tmp_path: Path) -> None:
    spec = tmp_path / "approved.md"
    _ = spec.write_text("# Approved\n", encoding="utf-8")

    assert classify_input(spec).kind is MoldCookInputKind.DIRECT_SPEC
    assert classify_input("approved-spec").kind is MoldCookInputKind.SLUG
    assert classify_input("implement the approved change").kind is MoldCookInputKind.TASK
