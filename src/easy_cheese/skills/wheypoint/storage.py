"""The on-disk work store: one living record, immutable revisions beside it.

    project_corpus_root()/work/<work-id>/
      record.json
      revisions/<revision-number>-<revision-id>.json
      projections/<revision-number>-<revision-id>.md

The write order is the whole crash-safety story, and `promote` is the only
place it exists: both immutable files are written and fsynced *first*, and
`record.json` is atomically replaced *last*. A machine that dies at any point
therefore leaves either the old record with some unreferenced immutable files,
or the new record with everything it points at fully on disk. It can never
leave a promoted record naming a receipt that is not there.

`recover` is the reader of that guarantee. It reconciles what is complete --
a receipt that structures, whose filename matches its own identity, and whose
projection is present and hashes to the digest the receipt claims -- and
*reports* anything else. It writes nothing, repairs nothing, and never fills a
gap with a guess: an interrupted promotion is a fact about the disk, not a
state to be invented.

Nothing here reaches outside the corpus. Durability is reported by the
projection; this module never publishes.
"""

from __future__ import annotations

import json
import os
import re
import tempfile
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from typing import cast

from attrs import define
from easy_cheese_schemas import LOWER_IDENTIFIER_RE, WheypointRecord, WheypointRevision

try:
    import fcntl  # POSIX advisory file locks
except ImportError:  # pragma: no cover - exercised only on Windows
    fcntl = None  # type: ignore[assignment]

from easy_cheese.shared import paths

from . import canonical
from . import projection as projection_mod
from . import records

WORK_DIRNAME = "work"
RECORD_FILENAME = "record.json"
REVISIONS_DIRNAME = "revisions"
PROJECTIONS_DIRNAME = "projections"
LOCK_FILENAME = "record.lock"
PENDING_DIRNAME = "pending"

# A work id is also a path segment here, so anything that could leave the
# corpus is refused before it is ever joined onto a root.
_WORK_ID_RE = LOWER_IDENTIFIER_RE
_LOCK_MODE = 0o600


class StorageError(RuntimeError):
    """Raised when the store is asked for something it must not do."""


@define(frozen=True)
class RevisionFile:
    """A receipt whose immutable pair is complete on disk."""

    revision: WheypointRevision
    path: Path
    projection_path: Path


@define(frozen=True)
class RevisionScan:
    """Every complete immutable revision, oldest first, plus a reason for
    every receipt or projection that was skipped rather than silently
    dropped: a caller that only reports the survivors is not the same as
    a caller that never lost anything.
    """

    files: tuple[RevisionFile, ...]
    skipped: tuple[str, ...]


@define(frozen=True)
class RecoveryReport:
    """What the store actually holds, with nothing filled in."""

    record: WheypointRecord | None
    complete: tuple[RevisionFile, ...]
    incomplete: tuple[str, ...]
    problems: tuple[str, ...]
    stamped_schema_version: int | None = None

    @property
    def consistent(self) -> bool:
        return self.record is not None and not self.problems

    @property
    def latest_complete(self) -> RevisionFile | None:
        return self.complete[-1] if self.complete else None

    @property
    def revision_ids(self) -> frozenset[str]:
        return frozenset(file.revision.revision_id for file in self.complete)


def file_digest(path: Path) -> str | None:
    """The digest of a file's bytes, or None when it is not there."""
    try:
        return canonical.digest_bytes(Path(path).read_bytes())
    except (FileNotFoundError, IsADirectoryError, NotADirectoryError):
        return None


def _lock(fd: int, *, exclusive: bool) -> None:
    if fcntl is not None:
        fcntl.flock(fd, fcntl.LOCK_EX if exclusive else fcntl.LOCK_UN)
    else:  # pragma: no cover - Windows only
        import msvcrt

        msvcrt.locking(fd, msvcrt.LK_LOCK if exclusive else msvcrt.LK_UNLCK, 1)


def _fsync_dir(path: Path) -> None:
    fd = os.open(str(path), os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def write_atomic(path: Path, payload: bytes) -> None:
    """Write `payload` to a sibling temp file, fsync it, then rename it in.

    The rename is the only moment `path` changes, so a reader sees the old
    bytes or the new bytes and never a partial file.
    """
    fd, tmp_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    tmp = Path(tmp_name)
    try:
        with os.fdopen(fd, "wb") as handle:
            _ = handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(str(tmp), str(path))
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise
    _fsync_dir(path.parent)


@define(frozen=True)
class WorkStore:
    """The store for one work id, anchored on the durable project corpus."""

    work_id: str
    root: Path

    @classmethod
    def open(cls, work_id: str, *, corpus_root: Path | str | None = None) -> WorkStore:
        if _WORK_ID_RE.fullmatch(work_id) is None:
            raise StorageError(
                f"work id {work_id!r} must match {_WORK_ID_RE.pattern} so it is a "
                + "single safe path segment"
            )
        base = (
            Path(corpus_root)
            if corpus_root is not None
            else paths.project_corpus_root()
        )
        return cls(work_id=work_id, root=base / WORK_DIRNAME / work_id)

    @property
    def record_path(self) -> Path:
        return self.root / RECORD_FILENAME

    @property
    def revisions_dir(self) -> Path:
        return self.root / REVISIONS_DIRNAME

    @property
    def projections_dir(self) -> Path:
        return self.root / PROJECTIONS_DIRNAME

    @property
    def lock_path(self) -> Path:
        return self.root / LOCK_FILENAME

    @property
    def pending_dir(self) -> Path:
        return self.root / PENDING_DIRNAME

    def pending_path(self, request_identity: str) -> Path:
        """The durable request ledger entry for one mirror transaction."""
        stem = request_identity.replace(":", "-")
        if stem.startswith(".") or re.fullmatch(r"[a-zA-Z0-9._-]+", stem) is None:
            raise StorageError("request identity is not a safe path segment")
        return self.pending_dir / f"{stem}.json"

    def remove_pending(self, request_identity: str) -> None:
        """Remove one request ledger entry and sync the directory."""
        path = self.pending_path(request_identity)
        try:
            path.unlink()
        except FileNotFoundError:
            return
        _fsync_dir(path.parent)

    def revision_path(self, number: int, revision_id: str) -> Path:
        return self.revisions_dir / f"{number}-{revision_id}.json"

    def projection_path(self, number: int, revision_id: str) -> Path:
        return self.projections_dir / f"{number}-{revision_id}.md"

    def relative_projection_path(self, number: int, revision_id: str) -> str:
        """The `projection_path` a receipt carries: relative to this work root."""
        return f"{PROJECTIONS_DIRNAME}/{number}-{revision_id}.md"

    @contextmanager
    def lock(self) -> Generator[None]:
        """Hold the exclusive per-record lock for the duration of the block."""
        self.root.mkdir(parents=True, exist_ok=True)
        fd = os.open(str(self.lock_path), os.O_RDWR | os.O_CREAT, _LOCK_MODE)
        try:
            _lock(fd, exclusive=True)
            yield
        finally:
            try:
                _lock(fd, exclusive=False)
            finally:
                os.close(fd)

    @classmethod
    def enumerate(cls, corpus_root: Path | str | None = None) -> list[WorkStore]:
        """Every work store under the corpus root that holds a record, by work id."""
        base = Path(corpus_root) if corpus_root is not None else paths.project_corpus_root()
        work_dir = base / WORK_DIRNAME
        stores: list[WorkStore] = []
        for record_path in sorted(work_dir.glob(f"*/{RECORD_FILENAME}")):
            # The same guard `open` enforces: a directory whose name is not a safe
            # work id is not a store, whatever it contains.
            if _WORK_ID_RE.fullmatch(record_path.parent.name) is None:
                continue
            stores.append(cls.open(record_path.parent.name, corpus_root=base))
        return stores

    def revisions(self) -> RevisionScan:
        """Every complete immutable revision, oldest first, plus a reason for
        every receipt or projection that was skipped rather than silently
        dropped: a caller that only reports the survivors is not the same as
        a caller that never lost anything.
        """
        complete: list[RevisionFile] = []
        incomplete: list[str] = []
        receipts: set[str] = set()
        if self.revisions_dir.is_dir():
            for path in sorted(self.revisions_dir.glob("*.json")):
                receipts.add(path.stem)
                reason, file = self._inspect_revision(path)
                if file is not None:
                    complete.append(file)
                else:
                    incomplete.append(f"{path.name}: {reason}")
        incomplete.extend(self._unclaimed_projections(receipts))
        complete.sort(key=lambda file: file.revision.revision_number)
        return RevisionScan(tuple(complete), tuple(incomplete))

    def read_record(self) -> WheypointRecord | None:
        try:
            raw = self.record_path.read_bytes()
        except FileNotFoundError:
            return None
        return records.structure(_parse_json(raw), WheypointRecord)

    def read_revision(self, number: int, revision_id: str) -> WheypointRevision | None:
        try:
            raw = self.revision_path(number, revision_id).read_bytes()
        except FileNotFoundError:
            return None
        return records.structure(_parse_json(raw), WheypointRevision)

    def revision_ids(self) -> frozenset[str]:
        """The ids of every complete immutable revision in this store."""
        return self.recover().revision_ids

    def find_complete_revision(self, revision_id: str) -> WheypointRevision | None:
        """The complete revision with this id, without knowing its number.

        A revision id names at most one file, so this reads that one pair
        rather than reconciling the whole store to answer a question about a
        single receipt.
        """
        if not self.revisions_dir.is_dir():
            return None
        for path in sorted(self.revisions_dir.glob(f"*-{revision_id}.json")):
            _, file = self._inspect_revision(path)
            if file is not None:
                return file.revision
        return None

    def promote(
        self,
        record: WheypointRecord,
        revision: WheypointRevision,
        markdown: str,
    ) -> None:
        """Write the immutable pair, then swap `record.json` in last.

        A *complete* revision is never rewritten: if this number and id already
        name a receipt whose projection is present and hashes to what the
        receipt claims, no property of the incoming triple can make it legal to
        replace a receipt a reader may already have quoted -- with one
        exception that replaces nothing. A retry that produces the *identical*
        receipt bytes over that complete pair is the tail of an interrupted
        promotion: the pair landed and the record swap did not. Finishing it
        writes only `record.json`, so the immutable half is compared, never
        touched.

        An incomplete pair left behind by an interrupted promotion is not that.
        `recover` reports it and never returns it as a revision, so nothing can
        have quoted it, and re-promoting the same number and id over it is how
        the interrupted attempt gets finished rather than a rewrite of history.

        The triple then has to agree before anything is written: a receipt that
        quotes a different record, or a projection that does not hash to the
        digest the receipt claims, is a bug upstream, and promoting it would
        make the store permanently unreadable.
        """
        revision_path = self.revision_path(
            revision.revision_number, revision.revision_id
        )
        projection_path = self.projection_path(
            revision.revision_number, revision.revision_id
        )
        payload = records.canonical_payload(revision)
        if revision_path.exists():
            _, existing = self._inspect_revision(revision_path)
            if existing is not None:
                if records.canonical_payload(existing.revision) != payload:
                    raise StorageError(
                        f"{revision_path.name} already exists and is immutable"
                    )
                # Identical receipt, and `_inspect_revision` has already proved
                # the projection beside it hashes to the digest that receipt
                # declares -- which `_check_agreement` is about to prove of
                # `markdown` too. The pair on disk is this promotion's pair, so
                # all that is left of it is the pointer.
                self._check_agreement(record, revision, markdown)
                write_atomic(self.record_path, records.canonical_payload(record))
                return

        self._check_agreement(record, revision, markdown)

        self.revisions_dir.mkdir(parents=True, exist_ok=True)
        self.projections_dir.mkdir(parents=True, exist_ok=True)

        write_atomic(revision_path, payload)
        write_atomic(projection_path, markdown.encode("utf-8"))
        write_atomic(self.record_path, records.canonical_payload(record))

    def _check_agreement(
        self,
        record: WheypointRecord,
        revision: WheypointRevision,
        markdown: str,
    ) -> None:
        if revision.work_id != record.work_id or record.work_id != self.work_id:
            raise StorageError(
                f"work id mismatch: store {self.work_id!r}, record "
                + f"{record.work_id!r}, revision {revision.work_id!r}"
            )
        if revision.revision_id != record.revision_id:
            raise StorageError(
                f"revision id mismatch: record {record.revision_id!r}, revision "
                + f"{revision.revision_id!r}"
            )
        if revision.revision_number != record.revision_number:
            raise StorageError(
                f"revision number mismatch: record {record.revision_number}, "
                + f"revision {revision.revision_number}"
            )
        if revision.record_digest != records.record_digest(record):
            raise StorageError("revision does not quote this record's digest")
        if record.revision_digest != records.revision_digest(revision):
            raise StorageError("record revision_digest does not name this revision")
        expected_path = self.relative_projection_path(
            revision.revision_number, revision.revision_id
        )
        if revision.projection_path != expected_path:
            raise StorageError(
                f"revision projection_path {revision.projection_path!r} is not "
                + f"{expected_path!r}"
            )
        if projection_mod.projection_digest_of_text(markdown) != (
            revision.projection_digest
        ):
            raise StorageError("projection text does not match its declared digest")

    def recover(self) -> RecoveryReport:
        """Reconcile what is on disk. Reads only; invents nothing."""
        scan = self.revisions()
        record, problems, stamped_schema_version = self._read_record_for_recovery()
        if record is not None:
            problems.extend(_record_problems(record, list(scan.files)))
        return RecoveryReport(
            record=record,
            complete=scan.files,
            incomplete=scan.skipped,
            problems=tuple(problems),
            stamped_schema_version=stamped_schema_version,
        )

    def _unclaimed_projections(self, receipts: set[str]) -> list[str]:
        """Projections no receipt on disk names.

        A receipt and its projection share a filename stem, so a projection
        with no `.json` beside it is half a promotion exactly as much as a
        receipt with no `.md`. Scanning only the receipts would leave a store
        holding a whole lineage in its readable half reporting nothing at all.
        """
        if not self.projections_dir.is_dir():
            return []
        return [
            f"{path.name}: no revision receipt names this projection"
            for path in sorted(self.projections_dir.glob("*.md"))
            if path.stem not in receipts
        ]

    def _inspect_revision(self, path: Path) -> tuple[str, RevisionFile | None]:
        try:
            payload = _parse_json(path.read_bytes())
        except ValueError:
            return "malformed JSON", None
        try:
            revision = records.structure(payload, WheypointRevision)
        except records.RecordError as exc:
            return f"not a readable revision: {exc}", None
        expected = self.revision_path(revision.revision_number, revision.revision_id)
        if path.name != expected.name:
            return "filename does not match the revision identity inside it", None
        projection_path = self.projection_path(
            revision.revision_number, revision.revision_id
        )
        try:
            text = projection_path.read_text(encoding="utf-8")
        except OSError:
            return "projection file is missing", None
        if projection_mod.projection_digest_of_text(text) != revision.projection_digest:
            return "projection digest mismatch", None
        return "", RevisionFile(
            revision=revision, path=path, projection_path=projection_path
        )

    def _read_record_for_recovery(
        self,
    ) -> tuple[WheypointRecord | None, list[str], int | None]:
        try:
            raw = self.record_path.read_bytes()
        except FileNotFoundError:
            return None, [], None
        try:
            payload = _parse_json(raw)
        except ValueError:
            return None, [f"{RECORD_FILENAME} is malformed JSON"], None
        stamped_schema_version = _stamped_version(payload)
        try:
            return (
                records.structure(payload, WheypointRecord),
                [],
                stamped_schema_version,
            )
        except records.RecordError as exc:
            return (
                None,
                [f"{RECORD_FILENAME} is not a readable record: {exc}"],
                stamped_schema_version,
            )


def _record_problems(
    record: WheypointRecord, complete: list[RevisionFile]
) -> list[str]:
    match = next(
        (
            file
            for file in complete
            if file.revision.revision_id == record.revision_id
            and file.revision.revision_number == record.revision_number
        ),
        None,
    )
    if match is None:
        return [
            f"{RECORD_FILENAME} points at revision {record.revision_id!r}, which is "
            + "not a complete immutable revision"
        ]
    problems: list[str] = []
    if match.revision.record_digest != records.record_digest(record):
        problems.append(
            f"{RECORD_FILENAME} does not match the record digest in revision "
            + f"{record.revision_id!r}"
        )
    if record.revision_digest != records.revision_digest(match.revision):
        problems.append(
            f"{RECORD_FILENAME} revision_digest does not match revision "
            + f"{record.revision_id!r}"
        )
    return problems


def _parse_json(raw: bytes) -> object:
    return cast(object, json.loads(raw.decode("utf-8")))


def _stamped_version(payload: object) -> int | None:
    """The `schema_version` a raw record claims, read before structuring."""
    if not isinstance(payload, dict):
        return None
    stamped = cast("dict[str, object]", payload).get("schema_version")
    return stamped if isinstance(stamped, int) else None
