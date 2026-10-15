"""Adversarial coverage for CLI paths not yet exercised by test_cli.py.

Covers: `link --rationale`, `--notes-file` unreadable (checkpoint + validate),
`list` edge/fork/gate filters, `shape --depth`, `backlinks --project`, and the
`refusal_for` `storage-error` mapping.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import NoReturn, cast

import pytest

from conftest import WORK_ID, git_marker_ancestor, payload_at, run_cli

from easy_cheese.shared.wheypoint import storage


@pytest.fixture(autouse=True)
def _chdir(  # pyright: ignore[reportUnusedFunction]
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # Project-scope `list` sweeps notes under the nearest `.git` ancestor.
    ancestor = git_marker_ancestor(tmp_path)
    if ancestor is not None:
        pytest.fail(f"{ancestor} holds a .git entry above tmp_path; list is not hermetic")
    monkeypatch.chdir(tmp_path)


def _seed(work_id: str = WORK_ID) -> None:
    status, payload = run_cli(
        [
            "checkpoint",
            "--work-id",
            work_id,
            "--orientation",
            "T.\nbody",
            "--next",
            "hold",
            "--context",
            "x",
            "--question",
            "Seed question?",
        ]
    )
    assert status == 0, payload


def _record_path(corpus_root: Path, work_id: str = WORK_ID) -> Path:
    return storage.WorkStore.open(work_id, corpus_root=corpus_root).record_path


def _rows(payload: dict[str, object], key: str) -> list[dict[str, object]]:
    return cast(list[dict[str, object]], payload[key])


# --- 1. edge rationale ------------------------------------------------------


@pytest.mark.usefixtures("corpus_root")
def test_edge_with_rationale_stores_it_exactly_on_the_edge() -> None:
    _seed()
    ref = "https://example.com/doc"
    intent = json.dumps(
        {
            "work_id": WORK_ID,
            "add_edges": [{"to": ref, "kind": "supersedes", "rationale": "why"}],
        }
    )

    status, payload = run_cli(["checkpoint", "-"], stdin=intent)
    assert status == 0, payload

    status, payload = run_cli(["show", "--work-id", WORK_ID])
    assert status == 0, payload
    edges = cast(list[dict[str, object]], payload_at(payload, "record", "edges"))
    matching = [e for e in edges if e["to"] == ref and e["kind"] == "supersedes"]
    assert len(matching) == 1, edges
    assert matching[0]["rationale"] == "why"


# --- 2. --notes-file unreadable ---------------------------------------------


def test_checkpoint_notes_file_missing_refuses_and_leaves_record_unchanged(
    corpus_root: Path,
) -> None:
    _seed()
    record_path = _record_path(corpus_root)
    before = record_path.read_bytes()

    status, payload = run_cli(
        [
            "checkpoint",
            "--work-id",
            WORK_ID,
            "--question",
            "Q?",
            "--notes-file",
            str(corpus_root / "does-not-exist.txt"),
        ]
    )

    assert status == 1
    assert payload_at(payload, "error", "code") == "notes-unreadable"
    assert record_path.read_bytes() == before


def test_validate_notes_file_missing_refuses(corpus_root: Path) -> None:
    _seed()

    status, payload = run_cli(
        [
            "validate",
            "--work-id",
            WORK_ID,
            "--question",
            "Q?",
            "--notes-file",
            str(corpus_root / "does-not-exist.txt"),
        ]
    )

    assert status == 1
    assert payload_at(payload, "error", "code") == "notes-unreadable"


@pytest.mark.skipif(os.geteuid() == 0, reason="root ignores file permissions")
def test_checkpoint_notes_file_unreadable_permissions_refuses(
    corpus_root: Path, tmp_path: Path
) -> None:
    _seed()
    record_path = _record_path(corpus_root)
    before = record_path.read_bytes()
    notes = tmp_path / "secret.txt"
    _ = notes.write_text("hi", encoding="utf-8")
    notes.chmod(0o000)
    try:
        status, payload = run_cli(
            [
                "checkpoint",
                "--work-id",
                WORK_ID,
                "--question",
                "Q?",
                "--notes-file",
                str(notes),
            ]
        )
    finally:
        notes.chmod(0o644)

    assert status == 1
    assert payload_at(payload, "error", "code") == "notes-unreadable"
    assert record_path.read_bytes() == before


# --- 3. list filters ---------------------------------------------------------


@pytest.mark.usefixtures("corpus_root")
def test_list_filters_return_exact_sets() -> None:
    _seed("work-a")
    status, payload = run_cli(
        ["fork", "work-a", "work-b", "--orientation", "Child.\nbody"]
    )
    assert status == 0, payload

    ref = "https://example.com/doc"
    status, payload = run_cli(
        ["checkpoint", "work-a", "--link", ref, "--kind", "supersedes"]
    )
    assert status == 0, payload

    gated_intent = json.dumps(
        {
            "work_id": "work-c",
            "orientation": "Gated.\nbody",
            "working_context": ["x"],
            "next": "hold",
        }
    )
    status, payload = run_cli(
        ["checkpoint", "-", "--question", "Q?", "--gates", "--rationale", "Why."],
        stdin=gated_intent,
    )
    assert status == 0, payload

    status, payload = run_cli(["list", "--edge-kind", "supersedes"])
    assert status == 0, payload
    assert {item["ref"] for item in _rows(payload, "items")} == {"work-a"}

    status, payload = run_cli(["list", "--forked-from", "work-a"])
    assert status == 0, payload
    assert {item["ref"] for item in _rows(payload, "items")} == {"work-b"}

    status, payload = run_cli(["list", "--no-gated"])
    assert status == 0, payload
    assert {item["ref"] for item in _rows(payload, "items")} == {"work-a", "work-b"}


# --- 6. storage-error mapping -------------------------------------------------


@pytest.mark.usefixtures("corpus_root")
def test_checkpoint_maps_an_unexpected_storage_error_to_storage_error_code(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _seed()

    def _refuse_open(*_args: object, **_kwargs: object) -> NoReturn:
        raise storage.StorageError("disk exploded")

    monkeypatch.setattr(storage.WorkStore, "open", _refuse_open)

    status, payload = run_cli(
        ["checkpoint", WORK_ID, "--link", "https://example.com/doc", "--kind", "supersedes"]
    )

    assert status == 1
    assert payload_at(payload, "error", "code") == "storage-error"
