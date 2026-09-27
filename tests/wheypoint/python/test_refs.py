"""Scheme-typed references: parse, normalize, resolve, digest, and pin."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import cast

import pytest
from easy_cheese_schemas import (
    ArtifactLink,
    IngressKind,
    WheypointDelta,
    WheypointRecord,
)

from easy_cheese.shared.wheypoint import canonical, commit, lint, records, refs, storage

from conftest import WORK_ID, Promotion, run_cli

PROJECT = "paulnsorensen-easy-cheese"
CAPTURED_AT = "2026-08-02T00:00:00Z"


def _delta(parent: str, **overrides: object) -> WheypointDelta:
    fields: dict[str, object] = {"work_id": WORK_ID, "expected_revision_id": parent}
    fields.update(overrides)
    return WheypointDelta(**fields)  # pyright: ignore[reportArgumentType]


def _seed(
    store: storage.WorkStore,
    make_promotion: Callable[..., Promotion],
    **overrides: object,
) -> Promotion:
    promotion = make_promotion(**overrides)
    store.promote(promotion.record, promotion.revision, promotion.markdown)
    return promotion


@pytest.fixture
def store(corpus_root: Path) -> storage.WorkStore:
    return storage.WorkStore.open(WORK_ID, corpus_root=corpus_root)


@pytest.fixture
def checkout(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    return root


def _first_intent(**fields: object) -> str:
    return json.dumps(
        {
            "work_id": WORK_ID,
            "orientation": "Genesis orientation.",
            "working_context": [],
            "next": "cook",
            "artifact": ".cheese/cook/refs.md",
            "notes": "First record.",
            "session": {"captured_at": CAPTURED_AT},
            **fields,
        }
    )


def _links(payload: dict[str, object]) -> list[dict[str, object]]:
    record = cast(dict[str, object], payload["record"])
    return cast(list[dict[str, object]], record["artifact_links"])


# AC-1: pinnable schemes resolve, digest, and pin the current revision.


def test_ac1_parse_ref_reads_every_scheme_form() -> None:
    assert refs.parse_ref("repo:docs/a.md") == refs.ParsedRef(
        scheme=refs.Scheme.REPO, path="docs/a.md", raw="repo:docs/a.md"
    )
    xdg = refs.parse_ref(f"xdg:{PROJECT}/specs/plan.md")
    assert (xdg.scheme, xdg.project_key, xdg.path) == (
        refs.Scheme.XDG,
        PROJECT,
        "specs/plan.md",
    )
    target = refs.parse_ref(f"wheypoint:{PROJECT}/work-0002@rev-0001#q-0001")
    assert (target.project_key, target.work_id, target.revision_id, target.entry_id) == (
        PROJECT,
        "work-0002",
        "rev-0001",
        "q-0001",
    )
    bare = refs.parse_ref(f"wheypoint:{PROJECT}/work-0002")
    assert (bare.revision_id, bare.entry_id) == (None, None)
    node = refs.parse_ref(f"milknado:{PROJECT}/node-7")
    assert (node.scheme, node.project_key, node.path) == (
        refs.Scheme.MILKNADO,
        PROJECT,
        "node-7",
    )
    assert refs.parse_ref("https://github.com/o/r/pull/1").scheme is refs.Scheme.HTTPS


@pytest.mark.parametrize(
    ("ref", "reason"),
    [
        ("ftp://host/file", "unknown-scheme"),
        ("docs/a.md", "unknown-scheme"),
        ("repo:../outside.md", "escapes"),
        ("repo:docs/../../outside.md", "escapes"),
        ("repo:/etc/passwd", "escapes"),
        (f"xdg:{PROJECT}/../other/doc.md", "escapes"),
        ("xdg:../doc.md", "escapes"),
        (f"xdg:{PROJECT}", "xdg:"),
        (f"wheypoint:{PROJECT}/Work 2", "wheypoint:"),
        ("milknado:node-7", "milknado:"),
        ("repo:", "repo:"),
    ],
)
def test_ac1_parse_ref_refuses_malformed_and_escaping_refs(ref: str, reason: str) -> None:
    with pytest.raises(ValueError, match=reason):
        _ = refs.parse_ref(ref)


def test_ac1_normalize_ref_yields_one_canonical_string() -> None:
    assert refs.normalize_ref("REPO:./docs//a.md/") == "repo:docs/a.md"
    assert refs.normalize_ref(f"Xdg:{PROJECT}/specs/./plan.md") == (
        f"xdg:{PROJECT}/specs/plan.md"
    )
    assert refs.normalize_ref(f"wheypoint:{PROJECT}/work-0002@rev-0001/") == (
        f"wheypoint:{PROJECT}/work-0002@rev-0001"
    )
    assert refs.normalize_ref("HTTPS://github.com/o/r/pull/1/") == (
        "https://github.com/o/r/pull/1"
    )


def test_ac1_resolve_and_digest_repo_and_xdg_files(checkout: Path, tmp_path: Path) -> None:
    home = tmp_path / "home"
    (home / PROJECT / "specs").mkdir(parents=True)
    doc = home / PROJECT / "specs" / "plan.md"
    _ = doc.write_text("plan", encoding="utf-8")
    _ = (checkout / "a.md").write_text("a", encoding="utf-8")

    resolved = refs.resolve_ref(
        f"xdg:{PROJECT}/specs/plan.md", checkout=checkout, corpus_home=home
    )
    assert resolved == refs.ResolvedRef(
        ref=f"xdg:{PROJECT}/specs/plan.md",
        scheme=refs.Scheme.XDG,
        location=doc,
        digest=canonical.digest_text("plan"),
    )
    assert refs.digest_ref("repo:a.md", checkout=checkout, corpus_home=home) == (
        canonical.digest_text("a")
    )
    assert refs.digest_ref("repo:absent.md", checkout=checkout, corpus_home=home) is None


def test_ac1_digest_refuses_a_symlink_that_escapes_its_root(
    checkout: Path, tmp_path: Path
) -> None:
    outside = tmp_path / "outside.md"
    _ = outside.write_text("secret", encoding="utf-8")
    (checkout / "link.md").symlink_to(outside)

    digest = refs.digester(checkout, tmp_path / "home")
    assert digest("repo:link.md") is None
    assert digest("repo:../outside.md") is None
    assert digest("not a ref") is None


def test_ac1_is_pinnable_splits_the_scheme_table() -> None:
    assert [scheme for scheme in refs.Scheme if refs.is_pinnable(scheme)] == [
        refs.Scheme.REPO,
        refs.Scheme.XDG,
        refs.Scheme.WHEYPOINT,
    ]


def test_ac1_xdg_ref_commits_with_its_digest_and_the_current_revision(
    store: storage.WorkStore,
    make_promotion: Callable[..., Promotion],
    corpus_root: Path,
    checkout: Path,
) -> None:
    (corpus_root / "specs").mkdir(parents=True)
    doc = corpus_root / "specs" / "plan.md"
    _ = doc.write_text("the plan", encoding="utf-8")
    seed = _seed(store, make_promotion)
    ref = f"xdg:{PROJECT}/specs/plan.md"

    result = commit.commit(
        _delta(
            seed.record.revision_id,
            add_artifact_links=[ArtifactLink(path="specs/plan.md", ref=ref)],
        ),
        store=store,
        artifact_root=checkout,
    )

    [link] = result.record.artifact_links
    assert link.ref == ref
    assert link.path == f"{PROJECT}/specs/plan.md"
    assert link.digest == storage.file_digest(doc)
    assert link.revision_id == result.record.revision_id


def test_ac1_repo_and_wheypoint_refs_pin_the_same_way(
    store: storage.WorkStore,
    make_promotion: Callable[..., Promotion],
    make_record: Callable[..., WheypointRecord],
    corpus_root: Path,
    checkout: Path,
) -> None:
    target_store = storage.WorkStore.open("work-0002", corpus_root=corpus_root)
    target = make_promotion(record=make_record(work_id="work-0002"))
    target_store.promote(target.record, target.revision, target.markdown)
    _ = (checkout / "docs").mkdir()
    _ = (checkout / "docs" / "a.md").write_text("a", encoding="utf-8")
    seed = _seed(store, make_promotion)

    result = commit.commit(
        _delta(
            seed.record.revision_id,
            add_artifact_links=[
                ArtifactLink(path="docs/a.md", ref="repo:./docs/a.md"),
                ArtifactLink(path="x", ref=f"wheypoint:{PROJECT}/work-0002"),
                ArtifactLink(path="x", ref=f"wheypoint:{PROJECT}/work-0002@rev-0001"),
            ],
        ),
        store=store,
        artifact_root=checkout,
    )

    repo_link, current_link, pinned_link = result.record.artifact_links
    assert (repo_link.ref, repo_link.path) == ("repo:docs/a.md", "docs/a.md")
    assert repo_link.digest == canonical.digest_text("a")
    assert current_link.digest == records.record_digest(target.record)
    assert pinned_link.digest == target.revision.record_digest
    assert {link.revision_id for link in result.record.artifact_links} == {
        result.record.revision_id
    }


def test_ac1_a_wheypoint_ref_naming_an_unknown_revision_is_refused(
    store: storage.WorkStore,
    make_promotion: Callable[..., Promotion],
    checkout: Path,
) -> None:
    seed = _seed(store, make_promotion)
    ref = f"wheypoint:{PROJECT}/{WORK_ID}@rev-9999"

    with pytest.raises(commit.CommitError, match="cannot digest"):
        _ = commit.commit(
            _delta(
                seed.record.revision_id,
                add_artifact_links=[ArtifactLink(path="x", ref=ref)],
            ),
            store=store,
            artifact_root=checkout,
        )
    assert store.read_record() == seed.record


def test_ac1_checkpoint_accepts_an_xdg_ref_link(
    corpus_root: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    (corpus_root / "specs").mkdir(parents=True)
    doc = corpus_root / "specs" / "plan.md"
    _ = doc.write_text("the plan", encoding="utf-8")
    ref = f"xdg:{PROJECT}/specs/plan.md"

    status, payload = run_cli(
        ["checkpoint"],
        stdin=_first_intent(artifact_links=[{"path": "specs/plan.md", "ref": ref}]),
    )

    assert status == 0, payload
    [link] = _links(payload)
    assert link["ref"] == ref
    assert link["digest"] == storage.file_digest(doc)
    record = cast(dict[str, object], payload["record"])
    assert link["revision_id"] == record["revision_id"]


def test_ac1_remove_artifact_links_accepts_a_path_or_a_ref(
    store: storage.WorkStore,
    make_promotion: Callable[..., Promotion],
    make_record: Callable[..., WheypointRecord],
    checkout: Path,
) -> None:
    carried = [ArtifactLink(path="a.md"), ArtifactLink(path="b.md")]
    seed = _seed(store, make_promotion, record=make_record(artifact_links=carried))

    result = commit.commit(
        _delta(seed.record.revision_id, remove_artifact_links=["a.md", "repo:./b.md"]),
        store=store,
        artifact_root=checkout,
    )

    assert result.record.artifact_links == []


# AC-2: a schema-3 record exposes path-only links as repo: refs, with receipts.


def test_ac2_v3_path_only_links_read_as_repo_refs_with_one_receipt_each(
    store: storage.WorkStore,
    make_promotion: Callable[..., Promotion],
    make_record: Callable[..., WheypointRecord],
) -> None:
    stored_links = [
        ArtifactLink(path=".cheese/cook/a.md"),
        ArtifactLink(path="docs/b.md", revision_id="rev-0001"),
    ]
    seed = _seed(
        store,
        make_promotion,
        record=make_record(schema_version=3, artifact_links=stored_links),
    )
    record = store.read_record()
    assert record is not None
    digest_before = records.record_digest(record)

    links, receipts = records.normalize_links(record)

    assert [link.ref for link in links] == ["repo:.cheese/cook/a.md", "repo:docs/b.md"]
    assert [link.path for link in links] == [".cheese/cook/a.md", "docs/b.md"]
    assert len(receipts) == 2
    for stored, normalized, receipt in zip(stored_links, links, receipts, strict=True):
        assert receipt.ingress_kind is IngressKind.LEGACY_ARTIFACT
        assert receipt.normalizer_id == "wheypoint.refs.v3-path-to-ref"
        assert receipt.source_digest == canonical.digest_bytes(
            records.canonical_payload(stored)
        )
        assert receipt.canonical_digest == canonical.digest_bytes(
            records.canonical_payload(normalized)
        )
        assert receipt.source_version is not None
        assert receipt.source_version.major == "3"
    # Read-side only: the stored record and its digest are unchanged.
    assert record.artifact_links == stored_links
    assert records.record_digest(record) == digest_before
    assert digest_before == seed.revision.record_digest


def test_ac2_lint_of_a_v3_record_reports_receipts_and_no_failure(
    store: storage.WorkStore,
    make_promotion: Callable[..., Promotion],
    make_record: Callable[..., WheypointRecord],
) -> None:
    _ = _seed(
        store,
        make_promotion,
        record=make_record(
            schema_version=3,
            artifact_links=[ArtifactLink(path="a.md"), ArtifactLink(path="b.md")],
        ),
    )

    report = lint.lint_work(
        store,
        project_key=PROJECT,
        git_object_exists=lambda _obj: True,
        artifact_digest=lambda _ref: None,
    )

    assert report.findings == ()
    assert len(report.normalizations) == 2


def test_ac2_a_link_that_carries_a_ref_needs_no_receipt(
    make_record: Callable[..., WheypointRecord],
) -> None:
    record = make_record(
        artifact_links=[ArtifactLink(path="a.md", ref="repo:a.md")],
    )

    links, receipts = records.normalize_links(record)

    assert links == tuple(record.artifact_links)
    assert receipts == ()
    assert records.effective_ref(ArtifactLink(path="x", ref="https://e.dev")) == (
        "https://e.dev"
    )


# AC-3: an unpinnable scheme may be linked but never cover an entry.


@pytest.mark.parametrize(
    "ref", [f"milknado:{PROJECT}/node-7", "https://github.com/o/r/pull/1"]
)
def test_ac3_an_unpinnable_ref_with_coverage_is_refused(
    ref: str,
    store: storage.WorkStore,
    make_promotion: Callable[..., Promotion],
    checkout: Path,
) -> None:
    seed = _seed(store, make_promotion, gating=True)
    entry_id = seed.record.questions[0].entry_id
    link = ArtifactLink(path="x", ref=ref, covers_entry_ids=[entry_id])

    with pytest.raises(commit.CommitError) as caught:
        _ = commit.commit(
            _delta(seed.record.revision_id, add_artifact_links=[link]),
            store=store,
            artifact_root=checkout,
        )

    assert str(caught.value).startswith("unpinnable-scheme: ")
    assert store.read_record() == seed.record


@pytest.mark.parametrize(
    "ref", [f"milknado:{PROJECT}/node-7", "https://github.com/o/r/pull/1"]
)
def test_ac3_an_unpinnable_ref_without_coverage_is_linked_with_no_digest(
    ref: str,
    store: storage.WorkStore,
    make_promotion: Callable[..., Promotion],
    checkout: Path,
) -> None:
    seed = _seed(store, make_promotion)

    result = commit.commit(
        _delta(
            seed.record.revision_id,
            add_artifact_links=[ArtifactLink(path="x", ref=ref)],
        ),
        store=store,
        artifact_root=checkout,
    )

    [link] = result.record.artifact_links
    assert link.ref == ref
    assert link.digest is None
    assert link.revision_id == result.record.revision_id


def test_ac3_checkpoint_reply_names_unpinnable_scheme(
    corpus_root: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    ref = f"milknado:{PROJECT}/node-7"
    link = {"path": "node-7", "ref": ref, "covers_entry_ids": ["q-durability"]}

    status, payload = run_cli(
        ["checkpoint"], stdin=_first_intent(artifact_links=[link])
    )

    assert status == 1
    error = cast(dict[str, str], payload["error"])
    assert "unpinnable-scheme: " in error["text"]
    assert not (corpus_root / "work" / WORK_ID / storage.RECORD_FILENAME).exists()


def test_ac3_coverage_on_an_unpinnable_ref_fails_the_claim(
    make_record: Callable[..., WheypointRecord],
) -> None:
    record = make_record(
        gating=True,
        artifact_links=[
            ArtifactLink(
                path="x",
                ref=f"milknado:{PROJECT}/node-7",
                revision_id="rev-0001",
                covers_entry_ids=["q-durability"],
            )
        ],
    )

    report = records.coverage_report(
        record,
        artifact_digest=lambda _ref: canonical.digest_text("x"),
        ancestor_revision_ids={"rev-0001"},
    )

    assert [failure.reason for failure in report.failures] == ["unpinnable-scheme"]
