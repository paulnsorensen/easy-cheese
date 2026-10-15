"""Move one record between people as a single canonical JSON bundle.

`export_bundle` freezes the current record into a bundle. `import_bundle`
verifies a bundle and writes it as the genesis of a fork child.

The bundle is one canonical JSON object (`canonical.canonical_bytes`):

* `record` and `projection`: the exported record, and its rendered projection;
* `record_digest`: the digest of the *exported* record;
* `projection_digest`: the digest of the projection text;
* `origin`: the source project, work id, revision id, and the digest of the
  unfiltered source record;
* `included`: which filtered kinds the author chose to keep;
* `bundle_digest`: the digest of the canonical bundle without this field.

Export drops operator-scope directives and local references unless asked.
Local references are links, edges, working-context items, and path-like words in
free text; a free-text word is replaced by `LOCAL_MARKER`. The checkout that
decides which paths are local is passed in, never read from the working
directory. A filtered record no longer matches the source digest, so `record_digest` covers
the record as exported and `origin` carries the source revision and digest
separately. A digest proves integrity, not authorship: whoever holds a bundle
can recompute every digest in it.

Import never trusts the bundle. It bounds the size, structures the record
against the schema, checks every digest, and writes nothing on any mismatch.
The child carries the record's orientation, next action, notes, working
context, artifact links, and active entries, plus one `forked_from` edge to
`wheypoint:<origin-project>/<work_id>@<revision_id>`. The origin project need
not exist on this machine: the edge is external lineage.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from pathlib import Path
from typing import cast

import attrs
from easy_cheese_schemas import (
    LOWER_IDENTIFIER_RE,
    ArtifactLink,
    Durability,
    EntryKind,
    EntryState,
    ProposedEntry,
    ProtectedEntry,
    RepositoryProvenance,
    SessionProvenance,
    WheypointDelta,
    WheypointRecord,
)
from easy_cheese_schemas.contracts import DirectiveScope, EdgeKind, WorkEdge

from easy_cheese.shared import paths

from . import canonical, commit, projection, records, refs, storage

__all__ = [
    "BUNDLE_VERSION",
    "LOCAL_MARKER",
    "MAX_BUNDLE_BYTES",
    "ImportOutcome",
    "TransferError",
    "export_bundle",
    "import_bundle",
    "parse_bundle",
    "target_store",
]

BUNDLE_VERSION = 1
LOCAL_MARKER = "<local reference omitted>"
MAX_BUNDLE_BYTES = 4 * 1024 * 1024
_BUNDLE_KEYS = frozenset(
    {
        "bundle_version",
        "origin",
        "included",
        "record",
        "record_digest",
        "projection",
        "projection_digest",
        "bundle_digest",
    }
)
_ORIGIN_KEYS = frozenset({"project_key", "work_id", "revision_id", "revision_number", "record_digest"})
_INCLUDED_KEYS = frozenset({"operator", "local"})
_DIGEST_RE = re.compile(r"sha256:[0-9a-f]{64}")
_WORD_RE = re.compile(r"\S+")


class TransferError(ValueError):
    """The bundle cannot be made or taken. The message starts with a `code:` prefix."""


def _link_text(link: ArtifactLink) -> str:
    ref = link.ref
    return link.path if ref is None or ref.startswith("repo:") else ref


def _needs_checkout(record: WheypointRecord) -> bool:
    """True when a link names a repository path, which only a checkout can classify."""
    return any(a.ref is None or a.ref.startswith("repo:") for a in record.artifact_links)


def _scrub(text: str, local: set[str]) -> str:
    """`text` with each local path-like word replaced by `LOCAL_MARKER`."""

    def word(match: re.Match[str]) -> str:
        found = projection.tokens(match.group())
        if len(found) == 1 and found[0] in local:
            return match.group().replace(found[0], LOCAL_MARKER)
        return match.group()

    return _WORD_RE.sub(word, text)


def _entry_texts(entry: ProtectedEntry) -> list[str]:
    return [t for t in (entry.summary, entry.rationale, entry.quote, entry.owner, entry.when) if t]


def _free_texts(record: WheypointRecord) -> list[str]:
    action = record.next_action
    texts = [record.title, record.orientation, record.notes or "", action.orientation]
    if action.artifact:
        texts.append(action.artifact)
    for entry in records.entries(record):
        texts.extend(_entry_texts(entry))
    return texts


def _scrub_entry(entry: ProtectedEntry, local: set[str]) -> ProtectedEntry:
    def clean(value: str | None) -> str | None:
        return None if value is None else _scrub(value, local)

    return attrs.evolve(
        entry,
        summary=_scrub(entry.summary, local),
        rationale=clean(entry.rationale),
        quote=clean(entry.quote),
        owner=clean(entry.owner),
        when=clean(entry.when),
    )


def _filtered(
    record: WheypointRecord,
    *,
    checkout: Path | None,
    include_operator: bool,
    include_local: bool,
) -> WheypointRecord:
    out = record
    if not include_operator:
        out = attrs.evolve(
            out,
            directives=[e for e in out.directives if e.scope is not DirectiveScope.OPERATOR],
        )
    if not include_local:
        if checkout is None and _needs_checkout(out):
            raise TransferError(
                "export-checkout-required: this record links repository paths, and "
                + "only a Git checkout says which are local; pass --workspace-root"
            )
        local = set(projection.local_references(out, checkout))
        scrubbed = projection.local_tokens(_free_texts(out), checkout)
        action = out.next_action
        artifact = action.artifact
        if artifact and (artifact in local or _scrub(artifact, scrubbed) != artifact):
            artifact = LOCAL_MARKER
        out = attrs.evolve(
            out,
            title=_scrub(out.title, scrubbed),
            orientation=_scrub(out.orientation, scrubbed),
            notes=None if out.notes is None else _scrub(out.notes, scrubbed),
            next_action=attrs.evolve(
                action, orientation=_scrub(action.orientation, scrubbed), artifact=artifact
            ),
            decisions=[_scrub_entry(e, scrubbed) for e in out.decisions],
            questions=[_scrub_entry(e, scrubbed) for e in out.questions],
            directives=[_scrub_entry(e, scrubbed) for e in out.directives],
            artifact_links=[a for a in out.artifact_links if _link_text(a) not in local],
            edges=tuple(e for e in out.edges if e.to not in local),
            working_context=[
                item
                for item in out.working_context
                if not any(t in local for t in projection.tokens(item))
            ],
        )
    return out


def export_bundle(
    record: WheypointRecord,
    *,
    checkout: Path | None,
    include_operator: bool = False,
    include_local: bool = False,
) -> dict[str, object]:
    """The bundle for `record`, with its record, projection, and bundle digests.

    `checkout` is the Git worktree that owns the record's repository paths.
    """
    exported = _filtered(
        record,
        checkout=checkout,
        include_operator=include_operator,
        include_local=include_local,
    )
    _, markdown = projection.build_projection(
        exported, durability=Durability.CANONICAL_LOCAL, checkout=checkout
    )
    body: dict[str, object] = {
        "bundle_version": BUNDLE_VERSION,
        "origin": {
            "project_key": record.project_key,
            "work_id": record.work_id,
            "revision_id": record.revision_id,
            "revision_number": record.revision_number,
            "record_digest": records.record_digest(record),
        },
        "included": {"operator": include_operator, "local": include_local},
        "record": records.unstructure(exported),
        "record_digest": records.record_digest(exported),
        "projection": markdown,
        "projection_digest": canonical.digest_text(markdown),
    }
    return {**body, "bundle_digest": canonical.digest_value(body)}


def _invalid(detail: str) -> TransferError:
    return TransferError(f"bundle-invalid: {detail}")


def _mismatch(what: str) -> TransferError:
    return TransferError(f"bundle-digest-mismatch: the {what} does not match its digest")


def _object(value: object, what: str, keys: frozenset[str]) -> dict[str, object]:
    if not isinstance(value, dict):
        raise _invalid(f"{what} must be a JSON object")
    found = cast("dict[str, object]", value)
    if frozenset(found) != keys:
        raise _invalid(f"{what} must hold exactly {', '.join(sorted(keys))}")
    return found


def _text(bundle: dict[str, object], key: str) -> str:
    value = bundle[key]
    if not isinstance(value, str):
        raise _invalid(f"{key} must be a string")
    return value


def parse_bundle(raw: bytes) -> tuple[WheypointRecord, dict[str, object]]:
    """The verified record and origin of a bundle; raises before anything is written."""
    try:
        return _parse(raw)
    except RecursionError as exc:
        raise _invalid("the bundle nests too deeply") from exc


def _is_int(value: object) -> bool:
    return type(value) is int


def _check_origin_and_included(
    bundle: dict[str, object],
    origin: dict[str, object],
    included: dict[str, object],
    record: WheypointRecord,
) -> None:
    if not all(type(v) is bool for v in included.values()):
        raise _invalid("included values must be booleans")
    if not _is_int(origin["revision_number"]) or origin["revision_number"] != record.revision_number:
        raise _invalid("origin.revision_number must be the record's revision number")
    digest = origin["record_digest"]
    if not isinstance(digest, str) or _DIGEST_RE.fullmatch(digest) is None:
        raise _invalid("origin.record_digest must be a sha256 digest")
    if not included["operator"] and any(
        e.scope is DirectiveScope.OPERATOR for e in record.directives
    ):
        raise _invalid("included says operator directives were dropped, but the record holds one")
    if not included["local"] and projection.local_references(record, None):
        raise _invalid("included says local references were dropped, but the record holds one")
    if included["operator"] and included["local"] and digest != bundle["record_digest"]:
        raise _invalid("origin.record_digest must match an unfiltered record")


def _parse(raw: bytes) -> tuple[WheypointRecord, dict[str, object]]:
    if len(raw) > MAX_BUNDLE_BYTES:
        raise _invalid(f"the bundle is larger than {MAX_BUNDLE_BYTES} bytes")
    try:
        loaded = cast(object, json.loads(raw))
    except ValueError as exc:
        raise _invalid(f"the bundle is not JSON: {exc}") from exc
    bundle = _object(loaded, "the bundle", _BUNDLE_KEYS)
    if not _is_int(bundle["bundle_version"]) or bundle["bundle_version"] != BUNDLE_VERSION:
        raise _invalid(f"bundle_version must be {BUNDLE_VERSION}")
    origin = _object(bundle["origin"], "origin", _ORIGIN_KEYS)
    included = _object(bundle["included"], "included", _INCLUDED_KEYS)
    body = {key: value for key, value in bundle.items() if key != "bundle_digest"}
    try:
        bundle_ok = canonical.digest_value(body) == bundle["bundle_digest"]
    except canonical.CanonicalJsonError as exc:
        raise _invalid(str(exc)) from exc
    if not bundle_ok:
        raise _mismatch("bundle")
    try:
        record = records.structure(bundle["record"], WheypointRecord, forbid_unknown=True)
    except records.RecordError as exc:
        raise _invalid(str(exc)) from exc
    markdown = _text(bundle, "projection")
    if records.record_digest(record) != bundle["record_digest"]:
        raise _mismatch("record")
    if canonical.digest_text(markdown) != bundle["projection_digest"]:
        raise _mismatch("projection")
    try:
        parsed = projection.parse(markdown)
    except projection.ProjectionParseError as exc:
        raise _invalid(f"the projection cannot be read: {exc}") from exc
    if (
        parsed.record_digest != bundle["record_digest"]
        or parsed.work_id != record.work_id
        or parsed.revision_id != record.revision_id
    ):
        raise _mismatch("projection identifiers")
    if (
        origin["work_id"] != record.work_id
        or origin["revision_id"] != record.revision_id
        or origin["project_key"] != record.project_key
    ):
        raise _mismatch("origin")
    _check_origin_and_included(bundle, origin, included, record)
    return record, origin


def _proposed(entry: ProtectedEntry) -> ProposedEntry:
    return ProposedEntry(
        kind=entry.kind,
        summary=entry.summary,
        blocks_continuation=entry.blocks_continuation,
        rationale=entry.rationale,
        quote=entry.quote,
        owner=entry.owner,
        when=entry.when,
        scope=entry.scope,
    )


def _active(record: WheypointRecord, kind: EntryKind) -> list[ProposedEntry]:
    return [
        _proposed(e)
        for e in records.entries(record)
        if e.kind is kind and e.state is EntryState.ACTIVE
    ]


def target_store(record: WheypointRecord, slug: str | None, corpus_root: Path) -> storage.WorkStore:
    """The empty store an import writes into; refuses a bad name or an existing record."""
    name = record.work_id if slug is None else slug
    if LOWER_IDENTIFIER_RE.fullmatch(name) is None:
        raise TransferError(f"invalid-slug: {name!r} is not a lower-case identifier")
    try:
        target = storage.WorkStore.open(name, corpus_root=corpus_root)
    except storage.StorageError as exc:
        raise TransferError(f"invalid-slug: {exc}") from exc
    if target.record_path.exists() or any(target.revisions_dir.glob("*.json")):
        raise TransferError(f"import-exists: work {name!r} already has a record or history")
    return target


@attrs.frozen
class ImportOutcome:
    """The commit, plus the artifact links the importer could not keep."""

    result: commit.CommitResult
    skipped_local: list[str]
    skipped_unresolvable: list[str]


def _digestible(link: ArtifactLink, digest_of: Callable[[str], str | None]) -> bool:
    """True when this machine can pin `link`, as `commit` will require."""
    try:
        ref = refs.pin_record(
            refs.normalize_ref(records.effective_ref(link)), corpus_home=paths.corpus_home()
        )
        scheme = refs.parse_ref(ref).scheme
    except ValueError:
        return False
    return not refs.is_pinnable(scheme) or digest_of(ref) is not None


def _genesis_stamps(record: WheypointRecord) -> tuple[int | None, int | None] | None:
    """Map the source notes drift onto the genesis revision.

    The genesis is revision 1, so a stamp from the source revision space would
    exceed the record's own `revision_number`. A drifted source imports as
    decisions stamped at 1 and notes unstamped, which keeps the drift marker.
    Any other source takes the default genesis stamps.
    """
    decisions = record.decisions_revision_number
    notes = record.notes_revision_number
    if decisions is not None and (notes is None or decisions > notes):
        return (None, 1)
    return None


def import_bundle(
    parsed: tuple[WheypointRecord, dict[str, object]],
    *,
    slug: str | None,
    corpus_root: Path,
    checkout: Path,
    session_provenance: SessionProvenance,
    repository: RepositoryProvenance | None = None,
    durability: Durability = Durability.CANONICAL_LOCAL,
    finalize: Callable[[commit.PendingRevision], None] | None = None,
) -> ImportOutcome:
    """Write a verified bundle (see `parse_bundle`) as a fork-child genesis named `slug`.

    `slug` defaults to the bundle record's work id. A name that is not a lower
    identifier, or that already holds a record, is refused. `checkout` is this
    machine's repository root; it digests the links. An absolute path is local
    here, because the author's paths do not exist on this machine. A local
    link, or one this machine cannot digest, is skipped and reported.
    """
    record, origin = parsed
    target = target_store(record, slug, corpus_root)
    source = f"wheypoint:{origin['project_key']}/{origin['work_id']}@{origin['revision_id']}"
    local = set(projection.local_references(record, None))
    digest_of = refs.digester(checkout, paths.corpus_home())
    skipped_local = [a for a in record.artifact_links if _link_text(a) in local]
    candidates = [a for a in record.artifact_links if _link_text(a) not in local]
    kept = [a for a in candidates if _digestible(a, digest_of)]
    skipped_unresolvable = [a for a in candidates if a not in kept]
    delta = WheypointDelta(
        work_id=target.work_id,
        expected_revision_id=commit.GENESIS_PARENT,
        orientation=record.orientation,
        working_context=list(record.working_context),
        notes=record.notes,
        next_action=record.next_action,
        add_decisions=_active(record, EntryKind.DECISION) or None,
        add_questions=_active(record, EntryKind.QUESTION) or None,
        add_directives=_active(record, EntryKind.DIRECTIVE) or None,
        add_artifact_links=[ArtifactLink(path=a.path, ref=a.ref) for a in kept] or None,
        session_provenance=session_provenance,
    )
    result = commit.commit(
        delta,
        store=target,
        repository=repository,
        durability=durability,
        artifact_root=checkout,
        fork_edge=WorkEdge(to=source, kind=EdgeKind.FORKED_FROM),
        imported_stamps=_genesis_stamps(record),
        finalize=finalize,
    )
    return ImportOutcome(
        result=result,
        skipped_local=[_link_text(a) for a in skipped_local],
        skipped_unresolvable=[_link_text(a) for a in skipped_unresolvable],
    )
