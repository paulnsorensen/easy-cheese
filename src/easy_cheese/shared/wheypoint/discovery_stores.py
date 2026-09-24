"""Store discovery: XDG work stores under one project corpus or every project."""

from __future__ import annotations

from pathlib import Path

from easy_cheese.shared import paths

from . import records, storage
from .discovery_types import Candidate, Hit


def _store_candidate(store: storage.WorkStore, project: str) -> Candidate | None:
    try:
        record = store.read_record()
    except (storage.StorageError, ValueError, OSError):
        return None
    if record is None:
        return None
    try:
        updated = store.record_path.stat().st_mtime
    except OSError:
        updated = 0.0
    resume = store.projection_path(record.revision_number, record.revision_id)
    orientation = record.orientation.strip().partition("\n")[0]
    haystack = "\n".join(
        [
            record.work_id,
            record.slug,
            record.title,
            record.orientation,
            *record.working_context,
            *(entry.summary for entry in records.entries(record)),
            record.notes or "",
        ]
    ).lower()
    hit = Hit(
        source="store",
        project=project,
        ref=record.work_id,
        status=record.status.value,
        next=record.next_action.move.value,
        orientation=orientation,
        updated=updated,
        path=store.record_path.resolve(),
        resume=resume.resolve(),
        revision_number=record.revision_number,
    )
    return Candidate(hit=hit, slug=record.slug, haystack=haystack)


def discover(
    *, corpus_root: Path | str | None, machine: bool
) -> tuple[list[Candidate], list[str], list[str]]:
    """Every readable store as a candidate, plus what was searched and errors.

    Machine scope walks every project directory under `paths.corpus_home()`;
    project scope reads the single given (or default) corpus root. The
    project key is the corpus directory name in both cases.
    """
    candidates: list[Candidate] = []
    searched: list[str] = []
    errors: list[str] = []
    roots: list[Path] = []
    if machine:
        home = paths.corpus_home()
        searched.append(str(home))
        try:
            roots = sorted(
                (path for path in home.iterdir() if path.is_dir()),
                key=lambda p: p.name,
            )
        except OSError as exc:
            errors.append(f"{home}: {exc}")
    else:
        root = (
            Path(corpus_root)
            if corpus_root is not None
            else paths.project_corpus_root()
        )
        roots = [root]
    for root in roots:
        searched.append(str(root))
        project = root.name
        try:
            stores = storage.WorkStore.enumerate(root)
        except OSError as exc:
            errors.append(f"{root}: {exc}")
            continue
        for store in stores:
            candidate = _store_candidate(store, project)
            if candidate is not None:
                candidates.append(candidate)
    return candidates, searched, errors
