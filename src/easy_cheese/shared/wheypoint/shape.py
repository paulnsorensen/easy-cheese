"""The work graph: records as nodes, their edges, and a Graphviz string.

`shape` reads every record under the selected project corpora without their
locks and returns one report. It never resolves, picks, or dispatches a
record: `resolve` remains the only authority. A node ref is
`wheypoint:<project_key>/<work_id>`, where the project key is the corpus
directory name. The `dot` string is deterministic: nodes sort by ref and
edges by `(from, to, kind)`, and it carries no timestamp.

Pending reciprocals and forks come from the records already loaded, so a
report reads each record once. Only a record that owes a reciprocal also
reads its own receipts, to drop the removals that stick.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Literal

from attrs import define, evolve
from easy_cheese_schemas import WheypointRecord, WheypointRevision
from easy_cheese_schemas.contracts import EdgeKind

from . import edges, fork_reconcile, lineage, records, storage
from .discovery_stores import normalized, work_key

__all__ = [
    "ShapeDocument",
    "ShapeEdge",
    "ShapeNode",
    "ShapeReport",
    "render_dot",
    "shape",
]

_LINEAGE = frozenset({EdgeKind.FORKED_FROM, EdgeKind.SUPERSEDED_BY})


@define(frozen=True, kw_only=True)
class ShapeNode:
    """One record in the graph; `updated` is the record file mtime."""

    ref: str
    project: str
    work_id: str
    title: str
    status: str
    next: str
    revision_number: int
    updated: float
    gates: tuple[str, ...]


@define(frozen=True, kw_only=True)
class ShapeEdge:
    """One edge `from_ref` holds, or owes when `pending` is set.

    A pending edge has no `revision_id`: no revision has written it yet.
    """

    from_ref: str
    to: str
    kind: EdgeKind
    revision_id: str | None
    pending: bool = False


@define(frozen=True, kw_only=True)
class ShapeDocument:
    """A non-`wheypoint:` ref and the node refs of the records that name it."""

    ref: str
    records: tuple[str, ...]


@define(frozen=True, kw_only=True)
class ShapeReport:
    """The graph `shape` found.

    `roots` are the node refs with no outgoing `forked_from` or
    `superseded_by` edge. `dangling` are the held edges whose `wheypoint:`
    target has no record.
    """

    nodes: tuple[ShapeNode, ...]
    edges: tuple[ShapeEdge, ...]
    pending: tuple[ShapeEdge, ...]
    documents: tuple[ShapeDocument, ...]
    roots: tuple[str, ...]
    dangling: tuple[ShapeEdge, ...]
    dot: str


@define(frozen=True)
class _Loaded:
    node: ShapeNode
    record: WheypointRecord
    corpus_root: Path
    store: storage.WorkStore


def _node_ref(project: str, work_id: str) -> str:
    return f"wheypoint:{project}/{work_id}"


def _target_ref(to: str) -> str:
    """The node ref a `wheypoint:` target names, pins dropped; else `to`."""
    key = work_key(to)
    return to if key is None else _node_ref(*key)


def _edge_order(edge: ShapeEdge) -> tuple[str, str, str]:
    return edge.from_ref, edge.to, edge.kind.value


def _project_roots(
    scope: Literal["project", "machine"],
    corpus_home: Path,
    project: str | None,
    projects: Sequence[str],
) -> list[Path]:
    if scope == "machine":
        try:
            names = sorted(path.name for path in corpus_home.iterdir() if path.is_dir())
        except OSError:
            names = []
        if projects:
            names = [name for name in names if name in projects]
    elif projects:
        names = list(projects)
    elif project is not None:
        names = [project]
    else:
        raise ValueError("shape --scope project needs a project key")
    return [corpus_home / name for name in dict.fromkeys(names)]


def _load(corpus_root: Path) -> list[_Loaded]:
    try:
        stores = storage.WorkStore.enumerate(corpus_root)
    except OSError:
        return []
    loaded: list[_Loaded] = []
    for store in stores:
        try:
            record = store.read_record()
        except (storage.StorageError, ValueError, OSError):
            continue
        if record is None:
            continue
        try:
            updated = store.record_path.stat().st_mtime
        except OSError:
            updated = 0.0
        node = ShapeNode(
            ref=_node_ref(corpus_root.name, record.work_id),
            project=corpus_root.name,
            work_id=record.work_id,
            title=record.title,
            status=record.status.value,
            next=record.next_action.move.value,
            revision_number=record.revision_number,
            updated=updated,
            gates=record.gating_entry_ids,
        )
        loaded.append(
            _Loaded(node=node, record=record, corpus_root=corpus_root, store=store)
        )
    return loaded


def _held(item: _Loaded) -> list[ShapeEdge]:
    return [
        ShapeEdge(
            from_ref=item.node.ref,
            to=normalized(edge.to),
            kind=edge.kind,
            revision_id=edge.revision_id,
        )
        for edge in item.record.edges
    ]


def _chain(item: _Loaded) -> tuple[WheypointRevision, ...]:
    """The receipts the current revision walks back through, as commit reads them."""
    receipts = item.store.receipt_revisions()
    current = next(
        (
            receipt
            for receipt in receipts
            if receipt.revision_id == item.record.revision_id
            and receipt.revision_number == item.record.revision_number
        ),
        None,
    )
    return () if current is None else tuple(lineage.walk(receipts, current).revisions)


def _owed(item: _Loaded, siblings: Sequence[WheypointRecord]) -> list[ShapeEdge]:
    owed_links = edges.pending_reciprocals(
        item.record, siblings=siblings, receipts=()
    )
    if owed_links:
        owed_links = edges.pending_reciprocals(
            item.record, siblings=siblings, receipts=_chain(item)
        )
    reciprocals = [
        ShapeEdge(
            from_ref=item.node.ref,
            to=owed.to,
            kind=owed.kind,
            revision_id=None,
            pending=True,
        )
        for owed in owed_links
    ]
    forks = [
        ShapeEdge(
            from_ref=item.node.ref,
            to=f"{owed.child_ref}@{owed.child_revision_id}",
            kind=EdgeKind.FORKED_TO,
            revision_id=None,
            pending=True,
        )
        for owed in fork_reconcile.pending_forks(item.record, siblings=siblings)
    ]
    return reciprocals + forks


def _resolves(key: tuple[str, str], corpus_home: Path) -> bool:
    project, work_id = key
    try:
        store = storage.WorkStore.open(work_id, corpus_root=corpus_home / project)
    except ValueError:
        return False
    return store.record_path.is_file()


def _component(
    seeds: Iterable[str], held: Iterable[ShapeEdge], depth: int | None
) -> set[str]:
    """Every ref within `depth` hops of a seed over edges in both directions."""
    neighbours: defaultdict[str, set[str]] = defaultdict(set)
    for edge in held:
        target = _target_ref(edge.to)
        neighbours[edge.from_ref].add(target)
        neighbours[target].add(edge.from_ref)
    reached = set(seeds)
    frontier = set(reached)
    hops = 0
    while frontier and (depth is None or hops < depth):
        frontier = {
            ref for current in frontier for ref in neighbours[current]
        } - reached
        reached |= frontier
        hops += 1
    return reached


def _documents(
    loaded: Iterable[_Loaded], held: Iterable[ShapeEdge]
) -> tuple[ShapeDocument, ...]:
    named: defaultdict[str, set[str]] = defaultdict(set)
    for edge in held:
        if work_key(edge.to) is None:
            named[edge.to].add(edge.from_ref)
    for item in loaded:
        for link in item.record.artifact_links:
            ref = normalized(records.effective_ref(link))
            if work_key(ref) is None:
                named[ref].add(item.node.ref)
    return tuple(
        ShapeDocument(ref=ref, records=tuple(sorted(owners)))
        for ref, owners in sorted(named.items())
        if len(owners) >= 2
    )


def shape(
    *,
    scope: Literal["project", "machine"],
    corpus_home: Path,
    project: str | None,
    projects: Sequence[str] = (),
    work_id: str | None = None,
    depth: int | None = None,
    kinds: Sequence[EdgeKind] = (),
) -> ShapeReport:
    """The graph of every record under the selected project corpora.

    `scope="project"` reads `corpus_home / project` (or each of `projects`);
    `scope="machine"` reads every project directory under `corpus_home`,
    narrowed to `projects` when given. `kinds` keeps only edges of those
    kinds; every node stays. `work_id` keeps the component within `depth`
    hops of each record with that id (unbounded when `depth` is None).
    """
    loaded = [
        item
        for root in _project_roots(scope, Path(corpus_home), project, projects)
        for item in _load(root)
    ]
    known = {(item.node.project, item.node.work_id) for item in loaded}
    by_corpus: defaultdict[Path, list[WheypointRecord]] = defaultdict(list)
    for item in loaded:
        by_corpus[item.corpus_root].append(item.record)
    all_held = [edge for item in loaded for edge in _held(item)]
    held = [edge for edge in all_held if not kinds or edge.kind in kinds]
    owed = [
        edge
        for item in loaded
        for edge in _owed(item, by_corpus[item.corpus_root])
        if not kinds or edge.kind in kinds
    ]
    if work_id is not None:
        seeds = [item.node.ref for item in loaded if item.node.work_id == work_id]
        keep = _component(seeds, held, depth)
        node_refs = {item.node.ref for item in loaded}
        loaded = [item for item in loaded if item.node.ref in keep]

        def inside(edge: ShapeEdge) -> bool:
            target = _target_ref(edge.to)
            return edge.from_ref in keep and (target in keep or target not in node_refs)

        all_held = [edge for edge in all_held if edge.from_ref in keep]
        held = [edge for edge in held if inside(edge)]
        owed = [edge for edge in owed if inside(edge)]
    lineage = {edge.from_ref for edge in all_held if edge.kind in _LINEAGE}
    dangling = [
        edge
        for edge in held
        if (key := work_key(edge.to)) is not None
        and key not in known
        and not _resolves(key, Path(corpus_home))
    ]
    nodes = tuple(sorted((item.node for item in loaded), key=lambda node: node.ref))
    report = ShapeReport(
        nodes=nodes,
        edges=tuple(sorted(held, key=_edge_order)),
        pending=tuple(sorted(owed, key=_edge_order)),
        documents=_documents(loaded, held),
        roots=tuple(node.ref for node in nodes if node.ref not in lineage),
        dangling=tuple(sorted(dangling, key=_edge_order)),
        dot="",
    )
    return evolve(report, dot=render_dot(report))


def _quote(text: str) -> str:
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'


def render_dot(report: ShapeReport) -> str:
    """A Graphviz digraph of `report`; the same report renders the same text.

    Pending edges are dashed and dangling edges red. An edge to a
    `wheypoint:` target points at the target's node, pins dropped.
    """
    dangling = set(report.dangling)
    lines = ["digraph wheypoint {"]
    for node in sorted(report.nodes, key=lambda node: node.ref):
        label = _quote(node.work_id)[:-1] + "\\n" + _quote(node.status)[1:]
        lines.append(f"  {_quote(node.ref)} [label={label}];")
    for edge in sorted((*report.edges, *report.pending), key=_edge_order):
        attributes = [f"label={_quote(edge.kind.value)}"]
        if edge.pending:
            attributes.append("style=dashed")
        if edge in dangling:
            attributes.append("color=red")
        lines.append(
            f"  {_quote(edge.from_ref)} -> {_quote(_target_ref(edge.to))} "
            + f"[{', '.join(attributes)}];"
        )
    lines.append("}")
    return "\n".join(lines) + "\n"
