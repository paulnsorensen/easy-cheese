"""AC-14: a checkpoint warns when decisions move but the notes stay put."""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast

import pytest

from conftest import WORK_ID, run_cli


def _checkpoint(**fields: object) -> dict[str, object]:
    status, payload = run_cli(
        ["checkpoint"], stdin=json.dumps({"work_id": WORK_ID, **fields})
    )
    assert status == 0, payload
    return payload


def _warnings(payload: dict[str, object]) -> list[str]:
    return cast(list[str], payload["warnings"])


@pytest.fixture(autouse=True)
def _genesis(  # pyright: ignore[reportUnusedFunction]
    corpus_root: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> dict[str, object]:
    """One committed record that already holds an active decision."""
    monkeypatch.chdir(tmp_path)
    _ = corpus_root
    return _checkpoint(
        orientation="Start.",
        working_context=["README.md"],
        next="cook",
        artifact=".cheese/cook/x.md",
        notes="Initial notes.",
        entries=[{"kind": "decision", "summary": "Use sqlite", "rationale": "simple"}],
    )


def _decision_id(genesis: dict[str, object]) -> str:
    decisions = cast(
        list[dict[str, object]],
        cast(dict[str, object], genesis["record"])["decisions"],
    )
    return cast(str, decisions[0]["entry_id"])


def test_stale_notes_warns_when_a_decision_is_added_without_notes() -> None:
    payload = _checkpoint(
        entries=[{"kind": "decision", "summary": "Use WAL", "rationale": "speed"}]
    )

    assert _warnings(payload) == ["stale-notes"]


def test_stale_notes_warns_when_a_decision_is_transitioned_without_notes(
    _genesis: dict[str, object],
) -> None:
    payload = _checkpoint(
        transitions=[
            {
                "entry_id": _decision_id(_genesis),
                "action": "withdraw",
                "rationale": "Dropped.",
            }
        ]
    )

    assert _warnings(payload) == ["stale-notes"]


def test_stale_notes_is_quiet_when_the_notes_are_replaced(
    _genesis: dict[str, object],
) -> None:
    payload = _checkpoint(
        notes="Fresh notes.",
        transitions=[
            {
                "entry_id": _decision_id(_genesis),
                "action": "withdraw",
                "rationale": "Dropped.",
            }
        ],
        entries=[{"kind": "decision", "summary": "Use WAL", "rationale": "speed"}],
    )

    assert _warnings(payload) == []


def test_stale_notes_is_quiet_for_a_question_only_delta() -> None:
    payload = _checkpoint(entries=[{"kind": "question", "summary": "Which index?"}])

    assert _warnings(payload) == []


def test_stale_notes_is_quiet_on_a_genesis_with_a_decision(
    _genesis: dict[str, object],
) -> None:
    assert _warnings(_genesis) == []


def test_stale_notes_is_quiet_when_the_record_never_had_notes() -> None:
    other = "no-notes-work"
    status, first = run_cli(
        ["checkpoint"],
        stdin=json.dumps(
            {
                "work_id": other,
                "orientation": "Start.",
                "working_context": ["README.md"],
                "next": "cook",
                "artifact": ".cheese/cook/y.md",
                "entries": [{"kind": "question", "summary": "Which index?"}],
            }
        ),
    )
    assert status == 0, first

    status, second = run_cli(
        ["checkpoint"],
        stdin=json.dumps(
            {
                "work_id": other,
                "entries": [
                    {"kind": "decision", "summary": "Use WAL", "rationale": "speed"}
                ],
            }
        ),
    )

    assert status == 0, second
    assert _warnings(second) == []
