"""Pytest config for the Wheypoint runtime suite (src/wheypoint/).

The runtime modules are flat, like src/fanout/: each is imported by bare name
so the same source runs from the repo and from the bundle wave 4 builds. They
also import `paths` from shared/scripts the same way, so both directories go on
sys.path here. `src/` and `vendor/` are already there from the repo-root
conftest.

The builders below assemble a *consistent* promotion -- record, revision, and
rendered projection whose digests agree -- because every storage and recovery
assertion is about what happens when exactly one of those three is wrong.
"""

from __future__ import annotations

import sys
from collections.abc import Callable
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
for _entry in (REPO_ROOT / "src" / "wheypoint", REPO_ROOT / "shared" / "scripts"):
    if str(_entry) not in sys.path:
        sys.path.insert(0, str(_entry))

from attrs import define, evolve  # noqa: E402
from easy_cheese_schemas import (  # noqa: E402
    SCHEMA_VERSION,
    DecisionFork,
    DossierOption,
    Durability,
    EntryKind,
    EntryState,
    NextAction,
    NextMove,
    ProtectedEntry,
    RepositoryProvenance,
    WheypointRecord,
    WheypointRevision,
)

import canonical  # noqa: E402
import projection  # noqa: E402
import records  # noqa: E402

PLACEHOLDER_DIGEST = "sha256:" + "0" * 64
WORK_ID = "work-0001"


@define(frozen=True)
class Promotion:
    """One consistent (record, revision, projection markdown) triple."""

    record: WheypointRecord
    revision: WheypointRevision
    markdown: str


def _next_action() -> NextAction:
    return NextAction(
        move=NextMove.COOK,
        orientation="Implement the canonical record runtime.",
        artifact=".cheese/cook/wheypoint-record-store-projection.md",
    )


def _gate_entry() -> ProtectedEntry:
    return ProtectedEntry(
        entry_id="q-durability",
        kind=EntryKind.QUESTION,
        summary="Should durability default to repo-snapshot?",
        state=EntryState.ACTIVE,
        blocks_continuation=True,
    )


def _dossier() -> DecisionFork:
    return DecisionFork(
        fork="Durability default",
        options=[
            DossierOption(
                option="canonical-local",
                evidence=["no git side effect"],
                breaks="nothing outside the corpus survives",
            )
        ],
        prior_leaning="canonical-local",
    )


def _record(**overrides: object) -> WheypointRecord:
    gating = bool(overrides.pop("gating", False))
    fields: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "work_id": WORK_ID,
        "slug": "wheypoint-continuity-kernel",
        "title": "Wheypoint continuity kernel",
        "created": "2026-08-02T00:00:00Z",
        "project_key": "paulnsorensen-easy-cheese",
        "revision_id": "rev-0001",
        "revision_number": 1,
        "revision_digest": PLACEHOLDER_DIGEST,
        "orientation": "Wave 2 owns storage and projection.",
        "working_context": ["src/wheypoint/storage.py"],
        "next_action": _next_action(),
        "decisions": [],
        "questions": [_gate_entry()] if gating else [],
        "blockers": [],
        "artifact_links": [],
        "decision_dossier": [_dossier()] if gating else [],
    }
    fields.update(overrides)
    return WheypointRecord(**fields)  # type: ignore[arg-type]


def _promotion(
    number: int = 1,
    revision_id: str = "rev-0001",
    *,
    parent: str | None = None,
    record: WheypointRecord | None = None,
    gating: bool = False,
) -> Promotion:
    base = record or _record(
        revision_id=revision_id, revision_number=number, gating=gating
    )
    projected, markdown = projection.build_projection(
        base, durability=Durability.CANONICAL_LOCAL
    )
    revision = WheypointRevision(
        schema_version=SCHEMA_VERSION,
        work_id=base.work_id,
        parent_revision_id=parent,
        revision_id=base.revision_id,
        revision_number=base.revision_number,
        request_digest=canonical.digest_text(f"request-{number}"),
        record_digest=records.record_digest(base),
        applied_additions=[],
        applied_transitions=[],
        preserved_entry_ids=[],
        projection_path=f"projections/{base.revision_number}-{base.revision_id}.md",
        projection_digest=projected.projection_digest,
        repository=RepositoryProvenance(branch="claude/wheypoint", commit="abc1234"),
    )
    # The record's pointer at its receipt is the last thing to settle: the
    # record digest deliberately excludes it, so this evolve does not
    # invalidate the digest the revision already quotes.
    return Promotion(
        record=evolve(base, revision_digest=records.revision_digest(revision)),
        revision=revision,
        markdown=markdown,
    )


@pytest.fixture
def make_record() -> Callable[..., WheypointRecord]:
    return _record


@pytest.fixture
def make_promotion() -> Callable[..., Promotion]:
    return _promotion


@pytest.fixture
def corpus_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A real project_corpus_root(), routed through its own env contract."""
    monkeypatch.setenv("EASY_CHEESE_HOME", str(tmp_path / "cheese"))
    monkeypatch.setenv("EASY_CHEESE_PROJECT", "paulnsorensen-easy-cheese")
    return tmp_path / "cheese" / "paulnsorensen-easy-cheese"