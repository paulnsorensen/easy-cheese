"""Checkpoint flags overlay the same intent payload a hand-written file carries."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest
from easy_cheese_schemas import CheckpointIntent, EntryKind, TransitionAction, load
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
        {
            "kind": "question",
            "summary": "Q",
            "blocks_continuation": True,
            "rationale": "Why.",
        },
        {"kind": "directive", "summary": "D", "quote": "d"},
    ],
}


def _flag_form(base: str | None = None) -> dict[str, object]:
    return intent_flags.overlay(
        {},
        work_id=WORK_ID,
        base=base,
        question=["Q"],
        gates=True,
        rationale=["Why."],
        directive=["D"],
        quote=["d"],
    )


def _intent(payload: dict[str, object]) -> CheckpointIntent:
    return records.structure(payload, CheckpointIntent, forbid_unknown=True)


def test_ac14_flags_build_the_hand_written_payload() -> None:
    assert _flag_form() == HAND_WRITTEN


def test_ac14_both_forms_fingerprint_the_same_delta(
    make_promotion: Callable[..., Promotion],
) -> None:
    current = make_promotion(gating=True).record

    base = current.revision_id
    flag_delta = checkpoint.build_delta(_intent(_flag_form(base)), current)
    file_delta = checkpoint.build_delta(
        _intent({**HAND_WRITTEN, "base_revision_id": base}), current
    )

    assert records.request_fingerprint(flag_delta) == records.request_fingerprint(
        file_delta
    )


def test_ac14_both_forms_commit_the_same_revision(
    tmp_path: Path, make_promotion: Callable[..., Promotion]
) -> None:
    revision_ids: list[str] = []
    for form in ("flags", "file"):
        store = storage.WorkStore.open(WORK_ID, corpus_root=tmp_path / form)
        seed = make_promotion(gating=True)
        store.promote(seed.record, seed.revision, seed.markdown)
        base = seed.record.revision_id
        payload = (
            _flag_form(base)
            if form == "flags"
            else {**HAND_WRITTEN, "base_revision_id": base}
        )
        delta = checkpoint.build_delta(_intent(payload), store.read_record())
        revision_ids.append(commit.commit(delta, store=store).record.revision_id)

    assert revision_ids[0] == revision_ids[1]
    assert revision_ids[0] != make_promotion(gating=True).record.revision_id


def test_overlay_appends_after_the_payload_and_overrides_scalars() -> None:
    payload: dict[str, object] = {
        "work_id": "from-file",
        "next": "cook",
        "working_context": ["a.py"],
        "entries": [{"kind": "question", "summary": "From the file."}],
    }

    result = intent_flags.overlay(
        payload,
        work_id=WORK_ID,
        question=["From a flag."],
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
            {"kind": "question", "summary": "From the file."},
            {
                "kind": "question",
                "summary": "From a flag.",
                "blocks_continuation": False,
            },
            {"kind": "decision", "summary": "Cap it.", "rationale": "Pool saturates."},
        ],
    }
    assert payload["entries"] == [{"kind": "question", "summary": "From the file."}]
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
        kind=["supersedes", "checkpoints"],
        covers=["q-aaaaaaaaaaaa"],
    )

    assert result["add_edges"] == [
        {"to": "repo:docs/spec.md", "kind": "supersedes"},
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
        EdgeKind.SUPERSEDES,
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
        ({"question": ["Q"], "gates": True}, "flag-pairing"),
        ({"covers": ["q-aaaaaaaaaaaa"]}, "flag-pairing"),
        ({"link": ["repo:a.md"], "kind": ["parent_of"]}, "flag-kind"),
        ({"link": ["nowhere:a"], "kind": ["checkpoints"]}, "flag-link"),
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


def test_supersede_flags_build_a_supersede_transition_with_its_successor() -> None:
    payload = intent_flags.overlay(
        {},
        work_id=WORK_ID,
        base="rev-0001",
        supersede=["d-old"],
        by=["d-new"],
        rationale=["Replaced."],
    )

    assert payload["transitions"] == [
        {
            "entry_id": "d-old",
            "action": "supersede",
            "rationale": "Replaced.",
            "target_entry_id": "d-new",
        }
    ]


def test_supersede_without_by_derives_the_id_of_the_one_added_entry() -> None:
    payload = intent_flags.overlay(
        {},
        work_id=WORK_ID,
        base="rev-0001",
        decision=["Use B"],
        supersede=["d-old"],
        rationale=["why", "Replaced."],
    )
    intent = _intent(payload)
    assert intent.entries is not None

    expected = commit.proposed_entry_id(
        WORK_ID, "rev-0001", EntryKind.DECISION, "Use B", False, 0
    )
    transitions = payload["transitions"]
    assert isinstance(transitions, list)
    assert transitions[0]["target_entry_id"] == expected


@pytest.mark.parametrize(
    "flags",
    [
        {"supersede": ["d-old"], "rationale": ["Replaced."]},
        {
            "supersede": ["d-old"],
            "rationale": ["Replaced."],
            "question": ["Q?"],
        },
        {
            "supersede": ["d-old"],
            "decision": ["B", "C"],
            "rationale": ["b", "c", "Replaced."],
        },
    ],
)
def test_supersede_pairing_refuses_when_no_successor_resolves(
    flags: dict[str, object],
) -> None:
    with pytest.raises(intent_flags.IntentFlagError, match="^flag-pairing"):
        _ = intent_flags.overlay({}, work_id=WORK_ID, base="rev-0001", **flags)  # pyright: ignore[reportArgumentType]


def test_supersede_pairing_refuses_a_by_count_that_differs() -> None:
    with pytest.raises(intent_flags.IntentFlagError, match="^flag-pairing"):
        _ = intent_flags.overlay(
            {},
            work_id=WORK_ID,
            supersede=["d-a", "d-b"],
            by=["d-c"],
            rationale=["x", "y"],
        )


def test_question_owner_and_when_pair_by_position_with_the_questions() -> None:
    payload = intent_flags.overlay(
        {},
        work_id=WORK_ID,
        question=["A?", "B?"],
        owner=["Ana", "Bo"],
        when=["soon", "later"],
    )

    assert _intent(payload).entries is not None
    assert payload["entries"] == [
        {
            "kind": "question",
            "summary": "A?",
            "blocks_continuation": False,
            "owner": "Ana",
            "when": "soon",
        },
        {
            "kind": "question",
            "summary": "B?",
            "blocks_continuation": False,
            "owner": "Bo",
            "when": "later",
        },
    ]


@pytest.mark.parametrize(
    "flags",
    [
        {"question": ["A?", "B?"], "owner": ["Ana"]},
        {"question": ["A?"], "when": ["soon", "later"]},
        {"owner": ["Ana"]},
    ],
)
def test_owner_and_when_counts_that_differ_from_question_refuse(
    flags: dict[str, object],
) -> None:
    with pytest.raises(intent_flags.IntentFlagError, match="^flag-pairing"):
        _ = intent_flags.overlay({}, work_id=WORK_ID, **flags)  # pyright: ignore[reportArgumentType]


def test_owner_on_a_non_question_is_refused_by_the_schema() -> None:
    payload = {
        "work_id": WORK_ID,
        "entries": [
            {"kind": "decision", "summary": "D", "rationale": "r", "owner": "Ana"}
        ],
    }

    loaded = load(payload, CheckpointIntent, strict=True, forbid_unknown=True)

    assert loaded.value is None
    assert any("owner" in problem for problem in loaded.problems)


def test_operator_directive_flag_adds_a_scope_operator_directive_after_work_ones() -> None:
    payload = intent_flags.overlay(
        {},
        work_id=WORK_ID,
        directive=["Work rule"],
        operator_directive=["Style rule"],
        quote=["work words", "style words"],
    )

    assert _intent(payload).entries is not None
    assert payload["entries"] == [
        {"kind": "directive", "summary": "Work rule", "quote": "work words"},
        {
            "kind": "directive",
            "summary": "Style rule",
            "quote": "style words",
            "scope": "operator",
        },
    ]


def test_operator_directive_without_its_quote_refuses_with_flag_pairing() -> None:
    with pytest.raises(intent_flags.IntentFlagError, match="^flag-pairing"):
        _ = intent_flags.overlay(
            {}, work_id=WORK_ID, operator_directive=["Style rule"]
        )


def test_scope_operator_on_a_question_is_refused_by_the_schema() -> None:
    payload = {
        "work_id": WORK_ID,
        "entries": [{"kind": "question", "summary": "Q?", "scope": "operator"}],
    }

    loaded = load(payload, CheckpointIntent, strict=True, forbid_unknown=True)

    assert loaded.value is None
    assert any("scope" in problem for problem in loaded.problems)
