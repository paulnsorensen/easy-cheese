"""Fork: one child genesis, a pending fork on read, host-side reconcile at checkpoint."""

from __future__ import annotations

from pathlib import Path

import pytest
from attrs import evolve
from easy_cheese_schemas import (
    ArtifactLink,
    DecisionFork,
    DossierOption,
    EntryKind,
    EntryState,
    EntryTransition,
    NextAction,
    NextMove,
    ProposedEntry,
    SessionProvenance,
    TransitionAction,
    WheypointDelta,
    WheypointRecord,
    WheypointStatus,
)
from easy_cheese_schemas.contracts import EdgeKind, WorkEdge, WorkEdgeKey

from easy_cheese.shared.wheypoint import (
    commit,
    fork,
    fork_reconcile,
    lint,
    projection,
    records,
    resolve as resolve_mod,
    resolve_cli,
    storage,
)

PROJECT = "paulnsorensen-easy-cheese"
LINK = "https://example.com/spec"
DOSSIER = "Edge owner"
CAPTURED = SessionProvenance(captured_at="2026-09-01T00:00:00Z")


def _ref(work_id: str) -> str:
    return f"wheypoint:{PROJECT}/{work_id}"


def _parent(corpus_root: Path, work_id: str = "parent") -> storage.WorkStore:
    store = storage.WorkStore.open(work_id, corpus_root=corpus_root)
    _ = commit.commit(
        WheypointDelta(
            work_id=work_id,
            expected_revision_id=commit.GENESIS_PARENT,
            orientation="Parent work.",
            working_context=["src/easy_cheese/shared/wheypoint/fork.py"],
            next_action=NextAction(move=NextMove.COOK, orientation="Keep going."),
            session_provenance=CAPTURED,
            add_questions=[
                ProposedEntry(
                    kind=EntryKind.QUESTION,
                    summary="Which store owns the edge?",
                    blocks_continuation=True,
                )
            ],
            add_directives=[
                ProposedEntry(
                    kind=EntryKind.DIRECTIVE,
                    summary="STE100 prose.",
                    quote="is it all in STE100?",
                )
            ],
            add_decisions=[
                ProposedEntry(
                    kind=EntryKind.DECISION, summary="Keep JSON.", rationale="digests"
                )
            ],
            decision_dossier=[
                DecisionFork(
                    fork=DOSSIER,
                    options=[
                        DossierOption(
                            option="the child", evidence=["F-2"], breaks="nothing"
                        )
                    ],
                )
            ],
            add_artifact_links=[ArtifactLink(path=LINK, ref=LINK)],
        ),
        store=store,
    )
    return store


def _record(store: storage.WorkStore) -> WheypointRecord:
    record = store.read_record()
    assert record is not None
    return record


def _ids(record: WheypointRecord) -> tuple[str, str, str]:
    return (
        record.questions[0].entry_id,
        record.directives[0].entry_id,
        record.decisions[0].entry_id,
    )


def _fork(corpus_root: Path, **overrides: object) -> commit.CommitResult:
    fields: dict[str, object] = {
        "parent": "parent",
        "child": "child",
        "corpus_root": corpus_root,
        "session_provenance": CAPTURED,
        "orientation": "Child work.\nOwns the edge question.",
    }
    fields.update(overrides)
    return fork.fork(**fields)  # pyright: ignore[reportArgumentType]


def _forked(corpus_root: Path) -> tuple[storage.WorkStore, commit.CommitResult]:
    parent = _parent(corpus_root)
    question, directive, _ = _ids(_record(parent))
    result = _fork(
        corpus_root,
        move=[question],
        copy=[directive],
        dossier=[DOSSIER],
        links=[LINK],
    )
    return parent, result


def _next(store: storage.WorkStore, **overrides: object) -> commit.CommitResult:
    current = _record(store)
    fields: dict[str, object] = {
        "work_id": store.work_id,
        "expected_revision_id": current.revision_id,
        "notes": f"Revision {current.revision_number + 1}.",
    }
    fields.update(overrides)
    return commit.commit(
        WheypointDelta(**fields),  # pyright: ignore[reportArgumentType]
        store=store,
    )


def _lint(store: storage.WorkStore) -> lint.LintReport:
    return lint.lint_work(
        store,
        project_key=PROJECT,
        git_object_exists=lambda _obj: True,
        artifact_digest=lambda _path: None,
    )


def _resolve(work_id: str, corpus_root: Path) -> resolve_mod.Resolution:
    return resolve_mod.resolve(
        work_id,
        corpus_root=corpus_root,
        project_key=PROJECT,
        git_object_exists=lambda _obj: True,
        artifact_digest=lambda _path: None,
    )


def _revision_files(corpus_root: Path) -> set[Path]:
    return set(corpus_root.glob("work/*/revisions/*.json"))


def _child_entry(record: WheypointRecord, kind: EntryKind) -> str:
    return next(e.entry_id for e in record.questions + record.directives if e.kind is kind)


def test_ac4_fork_writes_only_the_child_genesis(corpus_root: Path) -> None:
    parent = _parent(corpus_root)
    before = _record(parent)
    question, directive, _ = _ids(before)
    parent_bytes = parent.record_path.read_bytes()
    files = _revision_files(corpus_root)

    result = _fork(corpus_root, move=[question], copy=[directive], dossier=[DOSSIER])

    new_files = _revision_files(corpus_root) - files
    child = storage.WorkStore.open("child", corpus_root=corpus_root)
    assert [path.parent.parent.name for path in new_files] == ["child"]
    assert parent.record_path.read_bytes() == parent_bytes
    record = _record(child)
    assert record.revision_number == 1
    assert record.title == "Child work."
    pinned = f"{_ref('parent')}@{before.revision_id}"
    assert [(e.summary, e.origin) for e in record.questions] == [
        ("Which store owns the edge?", f"{pinned}#{question}")
    ]
    assert record.questions[0].blocks_continuation
    assert [(e.quote, e.origin) for e in record.directives] == [
        ("is it all in STE100?", f"{pinned}#{directive}")
    ]
    assert record.decisions == []
    assert [item.fork for item in record.decision_dossier] == [DOSSIER]
    assert record.edges == (
        WorkEdge(
            to=pinned,
            kind=EdgeKind.FORKED_FROM,
            revision_id=result.revision.revision_id,
            rationale=(
                f"fork of parent@{before.revision_id}; moved: {question}; "
                + f"copied: {directive}; dossier: {DOSSIER}; links: none"
            ),
        ),
    )


def test_ac5_lint_and_resolve_report_the_pending_fork(corpus_root: Path) -> None:
    parent, result = _forked(corpus_root)
    question, directive, _ = _ids(_record(parent))
    child = result.record
    child_question = _child_entry(child, EntryKind.QUESTION)
    child_directive = _child_entry(child, EntryKind.DIRECTIVE)

    report = _lint(parent)

    pending_findings = [
        f for f in report.findings if f.code is lint.LintCode.FORK_PENDING
    ]
    assert len(pending_findings) == 1
    assert lint.LintCode.LINK_PENDING not in report.codes
    assert not any(lint.gates_continuation(f) for f in pending_findings)
    detail = pending_findings[0].detail
    assert _ref("child") in detail and question in detail and directive in detail
    assert report.pending == ()
    assert report.pending_forks == (
        fork_reconcile.PendingFork(
            child_ref=_ref("child"),
            child_work_id="child",
            child_revision_id=child.revision_id,
            moved=((question, child_question),),
            copied=((directive, child_directive),),
            dossier_titles=(DOSSIER,),
            link_refs=(LINK,),
        ),
    )
    child_report = _lint(storage.WorkStore.open("child", corpus_root=corpus_root))
    assert (child_report.pending, child_report.pending_forks) == ((), ())
    assert lint.LintCode.LINK_PENDING not in child_report.codes

    resolution = _resolve("parent", corpus_root)
    payload = resolve_cli.resolve_payload(resolution, "parent")

    assert resolution.outcome is resolve_mod.ResolutionOutcome.GATED
    assert payload["pending"] == [
        {
            "kind": "fork",
            "child": _ref("child"),
            "revision_id": child.revision_id,
            "moved": [{"entry_id": question, "child_entry_id": child_question}],
            "copied": [{"entry_id": directive, "child_entry_id": child_directive}],
            "dossier": [DOSSIER],
            "links": [LINK],
        }
    ]


def test_ac6_the_parent_next_commit_applies_the_fork_host_side(
    corpus_root: Path,
) -> None:
    parent, forked = _forked(corpus_root)
    question, directive, decision = _ids(_record(parent))
    child = forked.record
    successor = f"{_ref('child')}#{_child_entry(child, EntryKind.QUESTION)}"
    copy = f"{_ref('child')}#{_child_entry(child, EntryKind.DIRECTIVE)}"

    result = _next(parent)

    record = _record(parent)
    moved = record.questions[0]
    assert (moved.entry_id, moved.state, moved.successor) == (
        question,
        EntryState.FORKED,
        successor,
    )
    assert record.directives[0].copies == (copy,)
    assert record.decisions[0].copies == ()
    assert record.decision_dossier == []
    assert record.artifact_links == []
    forked_to = WorkEdge(
        to=f"{_ref('child')}@{child.revision_id}",
        kind=EdgeKind.FORKED_TO,
        revision_id=record.revision_id,
        rationale=f"moved: {question}; copied: {directive}",
    )
    assert record.edges == (forked_to,)
    assert result.revision.applied_transitions == [
        EntryTransition(
            entry_id=question,
            action=TransitionAction.FORK,
            rationale=f"forked to {_ref('child')}",
            successor=successor,
        )
    ]
    assert result.revision.applied_edges == (forked_to,)
    assert sorted(result.revision.preserved_entry_ids) == sorted([directive, decision])
    assert lint.LintCode.FORK_PENDING not in _lint(parent).codes

    again = _next(parent)

    assert again.revision.applied_transitions == []
    assert again.revision.applied_edges == ()
    assert _record(parent).directives[0].copies == (copy,)


def test_ac6_an_agent_transition_on_a_moved_entry_wins_over_the_fork(
    corpus_root: Path,
) -> None:
    parent, _ = _forked(corpus_root)
    question, _, _ = _ids(_record(parent))
    resolved = EntryTransition(
        entry_id=question, action=TransitionAction.RESOLVE, rationale="settled here"
    )

    result = _next(parent, transitions=[resolved])

    assert result.revision.applied_transitions == [resolved]
    assert _record(parent).questions[0].state is EntryState.RESOLVED
    assert any(e.kind is EdgeKind.FORKED_TO for e in _record(parent).edges)


def test_ac7_a_parent_whose_only_gate_moved_resolves_ok(corpus_root: Path) -> None:
    parent, _ = _forked(corpus_root)
    question, _, _ = _ids(_record(parent))
    assert _record(parent).status is WheypointStatus.GATED

    result = _next(parent)

    assert result.record.status is WheypointStatus.OK
    assert result.record.gating_entry_ids == ()
    resolution = _resolve("parent", corpus_root)
    assert resolution.outcome is resolve_mod.ResolutionOutcome.AUTHORITATIVE
    body = result.markdown.split("## Lineage")
    assert question not in body[0].split("## Decisions")[0]
    assert f"- {question} successor " in body[1]
    assert list(projection.parse(result.markdown).gating_entry_ids) == []


def test_fork_defaults_move_questions_and_blockers_and_copy_the_rest(
    corpus_root: Path,
) -> None:
    parent = _parent(corpus_root)
    question, directive, decision = _ids(_record(parent))

    result = _fork(corpus_root)

    record = result.record
    assert [e.summary for e in record.questions] == ["Which store owns the edge?"]
    assert [e.summary for e in record.directives] == ["STE100 prose."]
    assert [e.summary for e in record.decisions] == ["Keep JSON."]
    assert [item.fork for item in record.decision_dossier] == [DOSSIER]
    assert record.artifact_links == []
    assert record.next_action.move is NextMove.HOLD
    assert record.edges[0].rationale is not None
    assert record.edges[0].rationale.endswith(
        f"moved: {question}; copied: {decision}, {directive}; "
        + f"dossier: {DOSSIER}; links: none"
    )


def test_fork_refuses_an_existing_child(corpus_root: Path) -> None:
    _ = _parent(corpus_root)
    _ = _parent(corpus_root, "child")

    with pytest.raises(fork.ForkError, match=r"^fork-exists: "):
        _ = _fork(corpus_root)


def test_fork_refuses_an_unknown_entry(corpus_root: Path) -> None:
    _ = _parent(corpus_root)

    with pytest.raises(fork.ForkError, match=r"^unknown-entry: "):
        _ = _fork(corpus_root, move=["q-000000000000"])

    assert not storage.WorkStore.open("child", corpus_root=corpus_root).record_path.exists()


def test_fork_refuses_an_entry_already_forked(corpus_root: Path) -> None:
    parent, _ = _forked(corpus_root)
    question, _, _ = _ids(_record(parent))
    _ = _next(parent)

    with pytest.raises(fork.ForkError, match=r"^already-forked: "):
        _ = _fork(corpus_root, child="grandchild", move=[question])


def test_fork_refuses_an_empty_selection(corpus_root: Path) -> None:
    parent = _parent(corpus_root)
    _ = _next(
        parent,
        transitions=[
            EntryTransition(
                entry_id=entry_id, action=TransitionAction.RESOLVE, rationale="done"
            )
            for entry_id in _ids(_record(parent))
        ],
        decision_dossier=[],
    )

    with pytest.raises(fork.ForkError, match=r"^fork-empty: "):
        _ = _fork(corpus_root)


def test_fork_refuses_a_split_too_large_for_the_edge_rationale(
    corpus_root: Path,
) -> None:
    parent = _parent(corpus_root)
    question, _, _ = _ids(_record(parent))

    with pytest.raises(fork.ForkError, match=r"^fork-too-large: "):
        _ = _fork(
            corpus_root,
            move=[question],
            copy=[f"v-{index:012d}" for index in range(200)],
        )


def test_commit_refuses_an_agent_authored_fork_transition(corpus_root: Path) -> None:
    parent = _parent(corpus_root)
    question, _, _ = _ids(_record(parent))
    before = parent.record_path.read_bytes()

    with pytest.raises(commit.CommitError, match="fork transitions are host-derived"):
        _ = _next(
            parent,
            transitions=[
                EntryTransition(
                    entry_id=question,
                    action=TransitionAction.FORK,
                    rationale="forged",
                    successor=f"{_ref('child')}#q-000000000000",
                )
            ],
        )

    assert parent.record_path.read_bytes() == before


def test_fork_refuses_an_entry_a_pending_fork_already_moves(corpus_root: Path) -> None:
    parent = _parent(corpus_root)
    question, directive, _ = _ids(_record(parent))
    _ = _fork(corpus_root, move=[question], copy=[directive], dossier=[DOSSIER])

    with pytest.raises(fork.ForkError, match=r"^already-forked: "):
        _ = _fork(corpus_root, child="second", move=[question], dossier=[DOSSIER])

    assert not storage.WorkStore.open("second", corpus_root=corpus_root).record_path.exists()
    assert [f.child_work_id for f in _lint(parent).pending_forks] == ["child"]


def test_two_pending_forks_of_one_entry_transition_it_once(corpus_root: Path) -> None:
    parent = _parent(corpus_root)
    current = _record(parent)
    question, _, _ = _ids(current)
    moved_to = "q-00000000000a"
    pending = tuple(
        fork_reconcile.PendingFork(
            child_ref=_ref(child),
            child_work_id=child,
            child_revision_id="rev-00000000000b",
            moved=((question, moved_to),),
            copied=(),
            dossier_titles=(),
            link_refs=(),
        )
        for child in ("child-a", "child-b")
    )

    applied = fork_reconcile.apply_pending_forks(current, pending)

    assert [(t.entry_id, t.successor) for t in applied.transitions] == [
        (question, f"{_ref('child-a')}#{moved_to}")
    ]
    assert applied.copies == {question: (f"{_ref('child-b')}#{moved_to}",)}
    assert [edge.to for edge in applied.edges] == [
        f"{_ref('child-a')}@rev-00000000000b",
        f"{_ref('child-b')}@rev-00000000000b",
    ]


def test_commit_refuses_a_fork_edge_in_a_delta(corpus_root: Path) -> None:
    _ = _parent(corpus_root)
    other = _parent(corpus_root, "other")
    before = other.record_path.read_bytes()

    for kind in (EdgeKind.FORKED_FROM, EdgeKind.FORKED_TO):
        with pytest.raises(commit.CommitError, match=r"^host-only-edge: "):
            _ = _next(
                other,
                add_edges=[WorkEdge(to=_ref("parent"), kind=kind, rationale="related")],
            )

    assert other.record_path.read_bytes() == before


def test_commit_refuses_a_delta_that_removes_a_fork_edge(corpus_root: Path) -> None:
    _ = _forked(corpus_root)
    child = storage.WorkStore.open("child", corpus_root=corpus_root)
    [edge] = [e for e in _record(child).edges if e.kind is EdgeKind.FORKED_FROM]
    before = child.record_path.read_bytes()

    with pytest.raises(commit.CommitError, match=r"^host-only-edge: "):
        _ = _next(child, remove_edges=[WorkEdgeKey(to=edge.to, kind=edge.kind)])

    assert child.record_path.read_bytes() == before


@pytest.mark.parametrize("title", ["Store | cache owner", "Store; cache owner"])
def test_fork_refuses_a_dossier_title_that_holds_a_rationale_separator(
    corpus_root: Path, title: str
) -> None:
    parent = _parent(corpus_root)
    _, directive, _ = _ids(_record(parent))
    option = DossierOption(option="x", evidence=["e"], breaks="y")
    _ = _next(parent, decision_dossier=[DecisionFork(fork=title, options=[option])])

    with pytest.raises(fork.ForkError, match=r"^fork-title: "):
        _ = _fork(corpus_root, copy=[directive], dossier=[title])

    assert not storage.WorkStore.open("child", corpus_root=corpus_root).record_path.exists()


def test_two_pending_forks_of_one_entry_reconcile_through_commit(
    corpus_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    parent = _parent(corpus_root)
    question, directive, _ = _ids(_record(parent))
    _ = _fork(
        corpus_root, child="child-a", move=[question], copy=[directive], dossier=[DOSSIER]
    )
    # A second fork that raced past the `already-forked` gate.
    def none_pending(
        _source: WheypointRecord, **_siblings: object
    ) -> tuple[fork_reconcile.PendingFork, ...]:
        return ()

    monkeypatch.setattr(fork, "pending_forks", none_pending)
    _ = _fork(
        corpus_root, child="child-b", move=[question], copy=[directive], dossier=[DOSSIER]
    )
    monkeypatch.undo()

    reconciled = _next(parent)

    [entry] = [e for e in records.entries(reconciled.record) if e.entry_id == question]
    assert entry.state is EntryState.FORKED
    assert entry.successor is not None and entry.successor.startswith(_ref("child-a"))
    assert [c.partition("#")[0] for c in entry.copies] == [_ref("child-b")]
    assert [t.entry_id for t in reconciled.revision.applied_transitions] == [question]
    assert _next(parent).revision.applied_transitions == []

def test_a_forked_from_edge_whose_rationale_does_not_parse_is_no_fork(
    corpus_root: Path,
) -> None:
    parent = _parent(corpus_root)
    other = _parent(corpus_root, "other")
    stray = evolve(
        _record(other),
        edges=(
            WorkEdge(
                to=_ref("parent"),
                kind=EdgeKind.FORKED_FROM,
                revision_id=_record(other).revision_id,
                rationale="just related",
            ),
        ),
    )

    assert fork_reconcile.pending_forks(_record(parent), siblings=[stray]) == ()


def test_reconcile_drops_only_the_links_and_dossier_selected_at_fork_time(
    corpus_root: Path,
) -> None:
    parent = _parent(corpus_root)
    question, directive, _ = _ids(_record(parent))
    _ = _next(
        parent,
        transitions=[
            EntryTransition(
                entry_id=question, action=TransitionAction.RESOLVE, rationale="done"
            )
        ],
    )
    _ = _fork(corpus_root, copy=[directive])
    child = storage.WorkStore.open("child", corpus_root=corpus_root)
    _ = _next(
        child,
        add_artifact_links=[ArtifactLink(path=LINK, ref=LINK)],
        decision_dossier=_record(parent).decision_dossier,
    )

    _ = _next(parent)

    record = _record(parent)
    assert [records.effective_ref(link) for link in record.artifact_links] == [LINK]
    assert [item.fork for item in record.decision_dossier] == [DOSSIER]
    assert record.directives[0].copies != ()


def test_fork_refuses_to_move_a_gate_without_a_dossier_fork(corpus_root: Path) -> None:
    parent = _parent(corpus_root)
    question, _, _ = _ids(_record(parent))

    with pytest.raises(fork.ForkError, match=r"^dossier-required: "):
        _ = _fork(corpus_root, move=[question])

    assert not storage.WorkStore.open("child", corpus_root=corpus_root).record_path.exists()


def test_a_retried_parent_promotion_ignores_a_fork_made_since_the_pair_landed(
    corpus_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    parent = _parent(corpus_root)
    current = _record(parent)
    question, directive, _ = _ids(current)
    delta = WheypointDelta(
        work_id="parent", expected_revision_id=current.revision_id, notes="Two."
    )
    old = parent.record_path.read_bytes()
    real = storage.WorkStore.promote

    def interrupted(
        self: storage.WorkStore,
        record: WheypointRecord,
        revision: object,
        markdown: str,
    ) -> None:
        real(self, record, revision, markdown)  # pyright: ignore[reportArgumentType]
        _ = self.record_path.write_bytes(old)

    monkeypatch.setattr(storage.WorkStore, "promote", interrupted)
    first = commit.commit(delta, store=parent)
    monkeypatch.setattr(storage.WorkStore, "promote", real)
    _ = _fork(corpus_root, move=[question], copy=[directive], dossier=[DOSSIER])

    retried = commit.commit(delta, store=parent)

    assert retried.revision.revision_id == first.revision.revision_id
    assert _record(parent).revision_id == first.revision.revision_id
    assert retried.revision.applied_transitions == []
    assert [f.child_work_id for f in _lint(parent).pending_forks] == ["child"]
