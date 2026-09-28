"""Checkpoint flags overlay the same intent payload a hand-written file carries."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest
from easy_cheese_schemas import CheckpointIntent, EntryKind, TransitionAction
from easy_cheese_schemas.contracts import EdgeKind

from easy_cheese.shared.wheypoint import (
    checkpoint,
    commit,
    intent_flags,
    records,
    storage,
)

from conftest import WORK_ID, Promotion

HAND_WRITTEN: dict[str, object] = {
    "work_id": WORK_ID,
    "entries": [
        {"kind": "question", "summary": "Q", "blocks_continuation": True},
        {"kind": "directive", "summary": "D", "quote": "d"},
    ],
}


def _flag_form() -> dict[str, object]:
    return intent_flags.overlay(
        {}, work_id=WORK_ID, question=["Q"], gates=True, directive=["D"], quote=["d"]
    )


def _intent(payload: dict[str, object]) -> CheckpointIntent:
    return records.structure(payload, CheckpointIntent, forbid_unknown=True)


def test_ac14_flags_build_the_hand_written_payload() -> None:
    assert _flag_form() == HAND_WRITTEN


def test_ac14_both_forms_fingerprint_the_same_delta(
    make_promotion: Callable[..., Promotion],
) -> None:
    current = make_promotion(gating=True).record

    flag_delta = checkpoint.build_delta(_intent(_flag_form()), current)
    file_delta = checkpoint.build_delta(_intent(HAND_WRITTEN), current)

    assert records.request_fingerprint(flag_delta) == records.request_fingerprint(
        file_delta
    )


def test_ac14_both_forms_commit_the_same_revision(
    tmp_path: Path, make_promotion: Callable[..., Promotion]
) -> None:
    revision_ids: list[str] = []
    for form, payload in (("flags", _flag_form()), ("file", HAND_WRITTEN)):
        store = storage.WorkStore.open(WORK_ID, corpus_root=tmp_path / form)
        seed = make_promotion(gating=True)
        store.promote(seed.record, seed.revision, seed.markdown)
        delta = checkpoint.build_delta(_intent(payload), store.read_record())
        revision_ids.append(commit.commit(delta, store=store).record.revision_id)

    assert revision_ids[0] == revision_ids[1]
    assert revision_ids[0] != make_promotion(gating=True).record.revision_id


def test_overlay_appends_after_the_payload_and_overrides_scalars() -> None:
    payload: dict[str, object] = {
        "work_id": "from-file",
        "next": "cook",
        "working_context": ["a.py"],
        "entries": [{"kind": "blocker", "summary": "From the file."}],
    }

    result = intent_flags.overlay(
        payload,
        work_id=WORK_ID,
        blocker=["From a flag."],
        decision=["Cap it."],
        rationale=["Pool saturates."],
        orientation="Oriented.",
        next="hold",
        artifact=".cheese/specs/x.md",
        context=["b.py"],
        notes="Body.",
    )

    assert result == {
        "work_id": WORK_ID,
        "next": "hold",
        "orientation": "Oriented.",
        "artifact": ".cheese/specs/x.md",
        "notes": "Body.",
        "working_context": ["a.py", "b.py"],
        "entries": [
            {"kind": "blocker", "summary": "From the file."},
            {"kind": "blocker", "summary": "From a flag.", "blocks_continuation": False},
            {"kind": "decision", "summary": "Cap it.", "rationale": "Pool saturates."},
        ],
    }
    assert payload["entries"] == [{"kind": "blocker", "summary": "From the file."}]
    assert payload["working_context"] == ["a.py"]


def test_resolve_and_withdraw_consume_rationales_after_the_decisions() -> None:
    result = intent_flags.overlay(
        None,
        work_id=WORK_ID,
        decision=["Cap it."],
        resolve=["q-aaaaaaaaaaaa"],
        withdraw=["b-bbbbbbbbbbbb"],
        rationale=["Pool saturates.", "Answered.", "Moot."],
    )

    intent = _intent(result)
    assert intent.entries is not None
    assert [(e.kind, e.rationale) for e in intent.entries] == [
        (EntryKind.DECISION, "Pool saturates.")
    ]
    assert intent.transitions is not None
    assert [(t.entry_id, t.action, t.rationale) for t in intent.transitions] == [
        ("q-aaaaaaaaaaaa", TransitionAction.RESOLVE, "Answered."),
        ("b-bbbbbbbbbbbb", TransitionAction.WITHDRAW, "Moot."),
    ]


def test_link_pairs_with_kind_and_pins_only_a_pinnable_scheme() -> None:
    result = intent_flags.overlay(
        {},
        work_id=WORK_ID,
        link=["repo:docs/spec.md", "milknado:proj/node-1"],
        kind=["informs", "checkpoints"],
        covers=["q-aaaaaaaaaaaa"],
    )

    assert result["add_edges"] == [
        {"to": "repo:docs/spec.md", "kind": "informs"},
        {"to": "milknado:proj/node-1", "kind": "checkpoints"},
    ]
    assert result["artifact_links"] == [
        {
            "path": "docs/spec.md",
            "ref": "repo:docs/spec.md",
            "covers_entry_ids": ["q-aaaaaaaaaaaa"],
        }
    ]
    intent = _intent(result)
    assert intent.add_edges is not None
    assert [edge.kind for edge in intent.add_edges] == [
        EdgeKind.INFORMS,
        EdgeKind.CHECKPOINTS,
    ]


@pytest.mark.parametrize(
    ("flags", "code"),
    [
        ({"decision": ["Cap it."]}, "flag-pairing"),
        ({"decision": ["Cap it."], "rationale": ["a", "b"]}, "flag-pairing"),
        ({"resolve": ["q-aaaaaaaaaaaa"]}, "flag-pairing"),
        ({"directive": ["D"]}, "flag-pairing"),
        ({"quote": ["d"]}, "flag-pairing"),
        ({"link": ["repo:a.md"]}, "flag-pairing"),
        ({"gates": True}, "flag-pairing"),
        ({"covers": ["q-aaaaaaaaaaaa"]}, "flag-pairing"),
        ({"link": ["repo:a.md"], "kind": ["parent_of"]}, "flag-kind"),
        ({"link": ["nowhere:a"], "kind": ["informs"]}, "flag-link"),
    ],
)
def test_overlay_refuses_flags_that_do_not_pair(
    flags: dict[str, object], code: str
) -> None:
    with pytest.raises(intent_flags.IntentFlagError, match=f"^{code}: "):
        _ = intent_flags.overlay({}, work_id=WORK_ID, **flags)  # pyright: ignore[reportArgumentType]


def test_overlay_refuses_a_payload_list_field_that_is_not_a_list() -> None:
    with pytest.raises(intent_flags.IntentFlagError, match="^flag-conflict: "):
        _ = intent_flags.overlay({"entries": "oops"}, question=["Q"])
