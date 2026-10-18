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

    assert status == 2
    assert payload_at(payload, "error", "code") == "invalid-intent"
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

    assert status == 2
    assert payload_at(payload, "error", "code") == "invalid-intent"
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

    assert status == 2
    assert payload_at(payload, "error", "code") == "invalid-intent"
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

    assert status == 2
    assert payload_at(payload, "error", "code") == "invalid-intent"
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

    assert status == 2
    assert payload_at(payload, "error", "code") == "invalid-intent"
    assert _record_path(corpus_root, "w-edge-5").read_bytes() == before

