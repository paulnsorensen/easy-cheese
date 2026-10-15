"""Baseline: real pre-v5 Wheypoint stores still recover under the current runtime.

The fixtures under `tests/wheypoint/fixtures/stores` are byte-for-byte copies of
lived stores, one per schema stamp. Each test copies a store into `tmp_path`
before it opens it, so a fixture is never mutated.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import cast

import pytest
from attrs import fields_dict
from easy_cheese_schemas import (
    SCHEMA_VERSION,
    Durability,
    EdgeKind,
    ProtectedEntry,
    WheypointDelta,
    WheypointRecord,
    WheypointStatus,
)

from easy_cheese.shared.wheypoint import commit, records, refs, resolve, storage
from easy_cheese.shared.wheypoint import projection as projection_mod

STORES_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "stores"
REMOVED_RECEIPT_KEYS = ("projection_digest", "preserved_entry_ids")

PRIOR_STORES = (
    pytest.param("v1", 1, id="v1"),
    pytest.param("v2", 2, id="v2"),
    pytest.param("v3", 3, id="v3"),
    pytest.param("v4", 4, id="v4"),
    pytest.param("v4-blocker", 4, id="v4-blocker"),
    pytest.param("v4-nonblocking-blocker", 4, id="v4-nonblocking-blocker"),
    pytest.param("contracts-simplify-v4", 4, id="contracts-simplify-v4"),
)


def load_json(path: Path) -> dict[str, object]:
    return cast(dict[str, object], json.loads(path.read_bytes()))


def open_fixture(name: str, tmp_path: Path) -> storage.WorkStore:
    """Copy one fixture store under `tmp_path/work/<work_id>` and open it."""
    source = STORES_DIR / name
    work_id = cast(str, load_json(source / "record.json")["work_id"])
    _ = shutil.copytree(source, tmp_path / storage.WORK_DIRNAME / work_id)
    return storage.WorkStore.open(work_id, corpus_root=tmp_path)


def tree_hashes(root: Path) -> dict[str, str]:
    return {
        str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def head_receipt_path(store: storage.WorkStore, record: WheypointRecord) -> Path:
    return store.revision_path(record.revision_number, record.revision_id)


@pytest.mark.parametrize(("name", "stamp"), PRIOR_STORES)
def test_prior_store_recovers_consistent(
    name: str, stamp: int, tmp_path: Path
) -> None:
    store = open_fixture(name, tmp_path)
    before = tree_hashes(store.root)

    report = store.recover()
    survey = store.survey_receipts()

    assert report.stamped_schema_version == stamp
    assert survey.stamped_schema_version == stamp
    assert report.problems == ()
    assert survey.problems == ()
    assert report.consistent
    assert report.incomplete == ()
    assert survey.incomplete == ()
    record = report.record
    assert record is not None
    assert survey.record == record
    assert record.schema_version == stamp
    assert report.complete, "fixture has no complete revision"
    assert len(survey.revisions) == len(report.complete)
    head = report.complete[-1].revision
    assert head.revision_id == record.revision_id
    assert head.revision_number == record.revision_number

    # Both digests agree with the raw bytes their writer hashed.
    raw_record = load_json(store.record_path)
    raw_receipt = load_json(head_receipt_path(store, record))
    assert raw_receipt["record_digest"] == records.stored_record_digest(
        raw_record, record
    )
    assert raw_record["revision_digest"] == records.stored_revision_digest(
        raw_receipt, head
    )
    for file in report.complete:
        revision = file.revision
        raw = load_json(store.revision_path(revision.revision_number, revision.revision_id))
        text = store.projection_path(
            revision.revision_number, revision.revision_id
        ).read_text(encoding="utf-8")
        assert raw["projection_digest"] == projection_mod.projection_digest_of_text(text)

    assert tree_hashes(store.root) == before, "a read wrote to the store"


def test_v4_blocker_fixture_is_gated_by_its_blocker() -> None:
    record = load_json(STORES_DIR / "v4-blocker" / "record.json")

    assert record["schema_version"] == 4
    blockers = cast(list[dict[str, object]], record["blockers"])
    assert [blocker["blocks_continuation"] for blocker in blockers] == [True]
    receipt = next((STORES_DIR / "v4-blocker" / "revisions").glob("*.json"))
    assert load_json(receipt)["schema_version"] == 4


def test_v4_fixture_carries_the_removed_receipt_fields() -> None:
    receipt = load_json(next((STORES_DIR / "v4" / "revisions").glob("*.json")))

    assert receipt["schema_version"] == 4
    assert cast(str, receipt["projection_digest"]).startswith("sha256:")
    assert receipt["preserved_entry_ids"] == []


def test_contracts_simplify_fixture_matches_source(tmp_path: Path) -> None:
    store = open_fixture("contracts-simplify-v4", tmp_path)

    report = store.recover()

    record = report.record
    assert record is not None
    assert record.schema_version == 4
    assert report.stamped_schema_version == 4
    assert report.problems == ()
    assert report.incomplete == ()
    head = report.complete[-1].revision
    assert head.revision_id == record.revision_id == "rev-d4db1d5e6d96"
    assert store.projection_path(head.revision_number, head.revision_id).is_file()
    raw = load_json(head_receipt_path(store, record))
    assert raw["preserved_entry_ids"], "compacted head must preserve entries"


@pytest.mark.parametrize(("name", "stamp"), PRIOR_STORES)
def test_checkpoint_over_prior_store_writes_v5_and_leaves_history_untouched(
    name: str, stamp: int, tmp_path: Path
) -> None:
    store = open_fixture(name, tmp_path)
    parent = store.read_record()
    assert parent is not None
    assert parent.schema_version == stamp
    before = tree_hashes(store.root)

    result = commit.commit(
        WheypointDelta(
            work_id=parent.work_id,
            expected_revision_id=parent.revision_id,
            orientation="Resumed after the v5 bump.",
        ),
        store=store,
    )

    after = tree_hashes(store.root)
    for relative, digest in before.items():
        if relative in {"record.json", "record.lock"}:
            continue
        assert after[relative] == digest, f"{relative} was rewritten"
    assert set(after) - set(before) == {
        f"revisions/{result.revision.revision_number}-{result.revision.revision_id}.json",
        f"projections/{result.revision.revision_number}-{result.revision.revision_id}.md",
    }

    report = store.recover()
    assert report.problems == ()
    raw_record = load_json(store.record_path)
    raw_receipt = load_json(
        store.revision_path(result.revision.revision_number, result.revision.revision_id)
    )
    assert raw_record["schema_version"] == SCHEMA_VERSION == 5
    assert raw_receipt["schema_version"] == SCHEMA_VERSION
    assert not set(REMOVED_RECEIPT_KEYS) & set(raw_receipt)
    # Agreement under v5 rules: the raw bytes hash to what each side quotes.
    assert raw_receipt["record_digest"] == records.stored_record_digest(
        raw_record, result.record
    )
    assert raw_record["revision_digest"] == records.stored_revision_digest(
        raw_receipt, result.revision
    )
    assert raw_receipt["parent_revision_id"] == parent.revision_id
    assert raw_receipt["parent_revision_digest"] == parent.revision_digest


@pytest.mark.parametrize("name", [param.values[0] for param in PRIOR_STORES])
def test_a_link_pin_never_reads_stale_over_an_unmodified_prior_store(
    name: str, tmp_path: Path
) -> None:
    """A head pin and a revision pin quote the same stored digest."""
    source = STORES_DIR / name
    raw_record = load_json(source / "record.json")
    work_id = cast(str, raw_record["work_id"])
    project = cast(str, raw_record["project_key"])
    _ = shutil.copytree(source, tmp_path / project / storage.WORK_DIRNAME / work_id)
    base = f"wheypoint:{project}/{work_id}"
    revision_id = cast(str, raw_record["revision_id"])

    head = refs.digest_ref(base, checkout=tmp_path, corpus_home=tmp_path)
    pinned = refs.digest_ref(
        f"{base}@{revision_id}", checkout=tmp_path, corpus_home=tmp_path
    )

    assert head is not None
    assert head == pinned
    receipt = load_json(
        next((source / "revisions").glob(f"*-{revision_id}.json"))
    )
    assert head == receipt["record_digest"]


@pytest.mark.parametrize(("name", "stamp"), PRIOR_STORES)
def test_prior_store_loads_as_v5(name: str, stamp: int, tmp_path: Path) -> None:
    """AC-1: a stamp<5 store reads as a v5-shaped record and the read writes nothing."""
    store = open_fixture(name, tmp_path)
    before = tree_hashes(store.root)

    record = store.read_record()

    assert record is not None
    assert record.schema_version == stamp
    record_fields = set(fields_dict(WheypointRecord))
    assert not {"blockers", "decision_dossier"} & record_fields
    assert not hasattr(record, "blockers")
    assert not hasattr(record, "decision_dossier")
    assert all(edge.kind in set(EdgeKind) for edge in record.edges)
    entry_fields = set(fields_dict(ProtectedEntry))
    assert not {"origin", "copies", "successor"} & entry_fields
    for entry in records.entries(record):
        assert not any(hasattr(entry, key) for key in ("origin", "copies", "successor"))
    assert tree_hashes(store.root) == before, "a read wrote to the store"


@pytest.mark.parametrize("name", [param.values[0] for param in PRIOR_STORES])
def test_prior_store_resolves_and_the_resolve_writes_nothing(
    name: str, tmp_path: Path
) -> None:
    store = open_fixture(name, tmp_path)
    record = store.read_record()
    assert record is not None
    before = tree_hashes(store.root)
    # The fixture workspace holds none of the linked artifacts, so each link
    # reads back its own stored digest; the check under test is the store.
    linked = {
        records.effective_ref(link): link.digest
        for link in record.artifact_links
        if link.digest is not None
    }

    resolution = resolve.resolve(
        record.work_id,
        corpus_root=tmp_path,
        project_key=record.project_key,
        workspace_root=tmp_path,
        artifact_digest=linked.get,
    )

    expected = (
        resolve.ResolutionOutcome.GATED
        if name == "v4-blocker"
        else resolve.ResolutionOutcome.AUTHORITATIVE
    )
    assert resolution.outcome is expected, resolution
    assert tree_hashes(store.root) == before, "resolve wrote to the store"


def test_v4_blocker_loads_as_a_blocking_question(tmp_path: Path) -> None:
    """AC-2: the blocker becomes a question with the same id and the same gate."""
    raw = load_json(STORES_DIR / "v4-blocker" / "record.json")
    blocker = cast(list[dict[str, object]], raw["blockers"])[0]
    store = open_fixture("v4-blocker", tmp_path)

    record = store.read_record()

    assert record is not None
    matches = [q for q in record.questions if q.entry_id == blocker["entry_id"]]
    assert len(matches) == 1
    question = matches[0]
    assert question.summary == blocker["summary"]
    assert question.blocks_continuation is True
    assert record.gating_entry_ids == (blocker["entry_id"],)
    assert record.status is WheypointStatus.GATED


def test_v4_nonblocking_blocker_stays_a_nonblocking_question(tmp_path: Path) -> None:
    """AC-2 (amended): a converted blocker keeps its stored gate and its status."""
    raw = load_json(STORES_DIR / "v4-nonblocking-blocker" / "record.json")
    blocker = cast(list[dict[str, object]], raw["blockers"])[0]
    assert blocker["blocks_continuation"] is False
    store = open_fixture("v4-nonblocking-blocker", tmp_path)

    record = store.read_record()

    assert record is not None
    matches = [q for q in record.questions if q.entry_id == blocker["entry_id"]]
    assert len(matches) == 1
    assert matches[0].summary == blocker["summary"]
    assert matches[0].blocks_continuation is False
    assert record.gating_entry_ids == ()
    assert record.status is WheypointStatus.OK


def test_contracts_simplify_projection_is_shorter(tmp_path: Path) -> None:
    """AC-13: the v5 projection of the lived record is at least 25% shorter."""
    store = open_fixture("contracts-simplify-v4", tmp_path)
    record = store.read_record()
    assert record is not None
    stored = store.projection_path(record.revision_number, record.revision_id)
    v4_chars = len(stored.read_text(encoding="utf-8"))

    _, markdown = projection_mod.build_projection(
        record, durability=Durability.CANONICAL_LOCAL
    )

    v5_chars = len(markdown)
    saved = 1 - v5_chars / v4_chars
    assert saved >= 0.25, f"v4={v4_chars} v5={v5_chars} saved={saved:.1%}"
