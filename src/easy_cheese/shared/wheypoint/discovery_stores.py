"""Store discovery: XDG work stores under one project corpus or every project."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from attrs import evolve
from easy_cheese_schemas.contracts import EdgeKind

from easy_cheese.shared import paths

from . import records, storage
from .discovery_types import Candidate, Hit
from .ref_grammar import Scheme, normalize_ref, parse_ref


def normalized(ref: str) -> str:
    """The canonical spelling of `ref`, or `ref` itself when it is malformed."""
    try:
        return normalize_ref(ref)
    except ValueError:
        return ref


def work_key(ref: str) -> tuple[str, str] | None:
    """The `(project_key, work_id)` a `wheypoint:` ref names, pins ignored."""
    try:
        parsed = parse_ref(ref)
    except ValueError:
        return None
    if (
        parsed.scheme is not Scheme.WHEYPOINT
        or parsed.project_key is None
        or parsed.work_id is None
    ):
        return None
    return parsed.project_key, parsed.work_id


def _store_candidate(
    store: storage.WorkStore, project: str
) -> tuple[Candidate | None, str | None]:
    try:
        record = store.read_record()
    except (storage.StorageError, ValueError, OSError) as exc:
        return None, f"{store.record_path}: {exc}"
    if record is None:
        return None, None
    try:
        updated = store.record_path.stat().st_mtime
    except OSError:
        updated = 0.0
    resume = store.projection_path(record.revision_number, record.revision_id)
    orientation = record.orientation.strip().partition("\n")[0]
    edges_out = tuple(
        sorted((edge.kind.value, normalized(edge.to)) for edge in record.edges)
    )
    links = tuple(
        normalized(records.effective_ref(link)) for link in record.artifact_links
    )
    forked_from = next(
        (
            key[1]
            for edge in record.edges
            if edge.kind is EdgeKind.FORKED_FROM
            and (key := work_key(edge.to)) is not None
        ),
        None,
    )
    haystack = "\n".join(
        [
            record.work_id,
            record.slug,
            record.title,
            record.orientation,
            *record.working_context,
            *(entry.summary for entry in records.entries(record)),
            record.notes or "",
            *(f"{kind} {to}" for kind, to in edges_out),
            *(edge.rationale for edge in record.edges if edge.rationale),
            *links,
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
        edges_out=edges_out,
        forked_from=forked_from,
        gates=record.gating_entry_ids,
    )
    entries = tuple(
        (entry.kind.value, entry.state.value) for entry in records.entries(record)
    )
    return (
        Candidate(
            hit=hit,
            slug=record.slug,
            haystack=haystack,
            entries=entries,
            links=links,
        ),
        None,
    )


def _with_edges_in(candidates: list[Candidate]) -> list[Candidate]:
    """Attach to each candidate the edges the other candidates point at it."""
    incoming: defaultdict[tuple[str, str], list[tuple[str, str]]] = defaultdict(list)
    for candidate in candidates:
        source = f"wheypoint:{candidate.hit.project}/{candidate.hit.ref}"
        for kind, to in candidate.hit.edges_out:
            key = work_key(to)
            if key is not None:
                incoming[key].append((kind, source))
    return [
        evolve(
            candidate,
            hit=evolve(
                candidate.hit,
                edges_in=tuple(
                    sorted(incoming.get((candidate.hit.project, candidate.hit.ref), ()))
                ),
            ),
        )
        for candidate in candidates
    ]


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
        except FileNotFoundError:
            roots = []
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
            candidate, error = _store_candidate(store, project)
            if candidate is not None:
                candidates.append(candidate)
            if error is not None:
                errors.append(error)
    return _with_edges_in(candidates), searched, errors
