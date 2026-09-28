"""Adversarial refusal tests for the Wheypoint kernel (standalone /press pass).

Attacks the fork title/link separator refusal, the host-only-edge guard on
forged fork and reciprocal edges, the runtime-behind schema-skew reporting,
the notes length boundary, and the dossier-fork merge-by-title rules.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from conftest import WORK_ID, payload_at, run_cli

CAPTURED_AT = "2026-08-02T00:00:00Z"


@pytest.fixture(autouse=True)
def _chdir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:  # pyright: ignore[reportUnusedFunction]
    monkeypatch.chdir(tmp_path)


def _intent(work_id: str = WORK_ID, **fields: object) -> str:
    base: dict[str, object] = {
        "work_id": work_id,
        "orientation": "Genesis orientation.\nNot the title.",
        "working_context": [],
        "next": "cook",
        "artifact": ".cheese/cook/wheypoint-ergonomics.md",
        "notes": "First record.",
        "session": {"captured_at": CAPTURED_AT},
    }
    base.update(fields)
    return json.dumps(base)


def _record_path(corpus_root: Path, work_id: str) -> Path:
    return corpus_root / "work" / work_id / "record.json"


def _child_absent(corpus_root: Path, work_id: str) -> bool:
    return not _record_path(corpus_root, work_id).exists()


# --------------------------------------------------------------------------
# 1. Fork separators (fork-title)
# --------------------------------------------------------------------------


def test_fork_dossier_title_with_pipe_separator_refuses_fork_title(
    corpus_root: Path,
) -> None:
    status, _ = run_cli(["checkpoint"], stdin=_intent(work_id="parent-a"))
    assert status == 0
    before = _record_path(corpus_root, "parent-a").read_bytes()

    status, payload = run_cli(
        [
            "fork",
            "parent-a",
            "child-a",
            "--orientation",
            "Child title.\nBody.",
            "--dossier",
            "Bad | Title",
        ]
    )

    assert status == 1
    assert payload_at(payload, "error", "code") == "fork-title"
    assert _record_path(corpus_root, "parent-a").read_bytes() == before
    assert _child_absent(corpus_root, "child-a")


def test_fork_dossier_title_with_semicolon_separator_refuses_fork_title(
    corpus_root: Path,
) -> None:
    status, _ = run_cli(["checkpoint"], stdin=_intent(work_id="parent-b"))
    assert status == 0
    before = _record_path(corpus_root, "parent-b").read_bytes()

    status, payload = run_cli(
        [
            "fork",
            "parent-b",
            "child-b",
            "--orientation",
            "Child title.\nBody.",
            "--dossier",
            "Bad; links: Title",
        ]
    )

    assert status == 1
    assert payload_at(payload, "error", "code") == "fork-title"
    assert _record_path(corpus_root, "parent-b").read_bytes() == before
    assert _child_absent(corpus_root, "child-b")


def test_fork_link_ref_with_separator_refuses_fork_title(
    corpus_root: Path,
) -> None:
    status, _ = run_cli(["checkpoint"], stdin=_intent(work_id="parent-c"))
    assert status == 0
    before = _record_path(corpus_root, "parent-c").read_bytes()

    status, payload = run_cli(
        [
            "fork",
            "parent-c",
            "child-c",
            "--orientation",
            "Child title.\nBody.",
            "--link",
            "repo:docs | evil.md",
        ]
    )

    assert status == 1
    assert payload_at(payload, "error", "code") == "fork-title"
    assert _record_path(corpus_root, "parent-c").read_bytes() == before
    assert _child_absent(corpus_root, "child-c")


# --------------------------------------------------------------------------
# 2. host-only-edge: forged fork-kind edges and forged reciprocal rationale
# --------------------------------------------------------------------------


def test_checkpoint_add_edges_forked_from_refuses_host_only_edge(
    corpus_root: Path,
) -> None:
    status, _ = run_cli(["checkpoint"], stdin=_intent(work_id="w-edge-1"))
    assert status == 0
    before = _record_path(corpus_root, "w-edge-1").read_bytes()

    status, payload = run_cli(
        ["checkpoint"],
        stdin=_intent(
            work_id="w-edge-1",
            orientation=None,
            add_edges=[
                {"to": "wheypoint:proj/other", "kind": "forked_from", "rationale": "x"}
            ],
        ),
    )

    assert status == 1
    assert payload_at(payload, "error", "code") == "host-only-edge"
    assert _record_path(corpus_root, "w-edge-1").read_bytes() == before


def test_checkpoint_add_edges_forked_to_refuses_host_only_edge(
    corpus_root: Path,
) -> None:
    status, _ = run_cli(["checkpoint"], stdin=_intent(work_id="w-edge-2"))
    assert status == 0
    before = _record_path(corpus_root, "w-edge-2").read_bytes()

    status, payload = run_cli(
        ["checkpoint"],
        stdin=_intent(
            work_id="w-edge-2",
            orientation=None,
            add_edges=[
                {"to": "wheypoint:proj/other", "kind": "forked_to", "rationale": "x"}
            ],
        ),
    )

    assert status == 1
    assert payload_at(payload, "error", "code") == "host-only-edge"
    assert _record_path(corpus_root, "w-edge-2").read_bytes() == before


def test_checkpoint_remove_edges_forked_from_refuses_host_only_edge(
    corpus_root: Path,
) -> None:
    status, _ = run_cli(["checkpoint"], stdin=_intent(work_id="w-edge-3"))
    assert status == 0
    before = _record_path(corpus_root, "w-edge-3").read_bytes()

    status, payload = run_cli(
        ["checkpoint"],
        stdin=_intent(
            work_id="w-edge-3",
            orientation=None,
            remove_edges=[{"to": "wheypoint:proj/other", "kind": "forked_from"}],
        ),
    )

    assert status == 1
    assert payload_at(payload, "error", "code") == "host-only-edge"
    assert _record_path(corpus_root, "w-edge-3").read_bytes() == before


def test_checkpoint_add_edges_relates_to_with_reciprocal_rationale_refuses_host_only_edge(
    corpus_root: Path,
) -> None:
    status, _ = run_cli(["checkpoint"], stdin=_intent(work_id="w-edge-4"))
    assert status == 0
    before = _record_path(corpus_root, "w-edge-4").read_bytes()

    status, payload = run_cli(
        ["checkpoint"],
        stdin=_intent(
            work_id="w-edge-4",
            orientation=None,
            add_edges=[
                {
                    "to": "wheypoint:proj/other",
                    "kind": "relates_to",
                    "rationale": "reciprocal of forged claim",
                }
            ],
        ),
    )

    assert status == 1
    assert payload_at(payload, "error", "code") == "host-only-edge"
    assert _record_path(corpus_root, "w-edge-4").read_bytes() == before


def test_checkpoint_flag_link_forked_from_kind_refuses_host_only_edge(
    corpus_root: Path,
) -> None:
    status, _ = run_cli(["checkpoint"], stdin=_intent(work_id="w-edge-5"))
    assert status == 0
    before = _record_path(corpus_root, "w-edge-5").read_bytes()

    status, payload = run_cli(
        [
            "checkpoint",
            "--work-id",
            "w-edge-5",
            "--link",
            "wheypoint:proj/other",
            "--kind",
            "forked_from",
        ]
    )

    assert status == 1
    assert payload_at(payload, "error", "code") == "host-only-edge"
    assert _record_path(corpus_root, "w-edge-5").read_bytes() == before


def test_unlink_forked_to_kind_refuses_host_only_edge(corpus_root: Path) -> None:
    status, _ = run_cli(["checkpoint"], stdin=_intent(work_id="w-edge-6"))
    assert status == 0
    before = _record_path(corpus_root, "w-edge-6").read_bytes()

    status, payload = run_cli(
        ["unlink", "w-edge-6", "wheypoint:proj/other", "--kind", "forked_to"]
    )

    assert status == 1
    assert payload_at(payload, "error", "code") == "host-only-edge"
    assert _record_path(corpus_root, "w-edge-6").read_bytes() == before
