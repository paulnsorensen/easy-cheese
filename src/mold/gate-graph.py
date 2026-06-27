#!/usr/bin/env python3
"""Render mold's gate state machine from one in-memory model.

`GATE_MODEL` is the single source of truth for mold's gate flow: the six modes,
the curdle terminal, and the coherence-checklist gates that guard the two-key
handshake. Both render targets derive from it, so they cannot drift:

  - `to_dot()` emits a canonical Graphviz `.dot` document.
  - `to_mermaid()` emits a GitHub/markdown-native `flowchart` block (no binary).

`render()` picks the target: `dot`/`svg`/`png` need Graphviz `dot` on PATH; when
it is absent it degrades to `mermaid` text so the tool runs anywhere (ADR-001).

The `gate` nodes double as the gate-prose-sync source: a test asserts they match
the coherence-checklist items in `skills/mold/references/handshake.md`, so a gate
cannot be silently dropped from prose (the rigor-parity mechanic). Gate ids are
the slugified checklist label up to its first colon, keeping the model and the
prose checklist in lockstep through one stable key.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

RENDER_TARGETS = ("dot", "svg", "png", "mermaid")
BINARY_TARGETS = {"svg", "png"}


@dataclass(frozen=True)
class Node:
    id: str
    label: str
    kind: str  # "mode" | "gate" | "terminal" | "handshake"


@dataclass(frozen=True)
class Edge:
    src: str
    dst: str
    label: str = ""


@dataclass(frozen=True)
class GateModel:
    nodes: tuple[Node, ...]
    edges: tuple[Edge, ...] = field(default_factory=tuple)

    def by_kind(self, kind: str) -> tuple[Node, ...]:
        return tuple(n for n in self.nodes if n.kind == kind)

    def ids(self) -> set[str]:
        return {n.id for n in self.nodes}


def _gate(label: str) -> Node:
    """A gate node whose id is the slug of the checklist label before its colon —
    the stable key shared with the handshake coherence checklist."""
    return Node(id=gate_id(label), label=label, kind="gate")


def gate_id(checklist_label: str) -> str:
    """Slug a coherence-checklist label into a gate id: take the text up to the
    first colon (the gate's name), lowercase, non-alphanumerics to single dashes.
    `handshake.md` and the model both run through this, so the two stay in sync."""
    head = checklist_label.split(":", 1)[0]
    slug = re.sub(r"[^a-z0-9]+", "-", head.strip().lower()).strip("-")
    return slug


# The 12 coherence-checklist gates, verbatim from handshake.md's checklist (the
# text before each colon is the gate's name; gate_id() slugs it). Order matches
# the prose so a diff between the two is legible.
COHERENCE_GATES: tuple[str, ...] = (
    "Problem statement: grounded, agreed",
    "At least 2 options weighed (Do Nothing included)",
    "Chosen option grounded in codebase evidence",
    "Interface sketches: every public seam has a pseudocode signature",
    "Cross-module calls go through public interfaces, not internals",
    "Identity nouns: each bound to a code referent or marked NEW ENTITY (an ALIAS must be resolved, not just noted)",
    "Non-goals audit: every bullet traces to a user-stated out-of-scope item or is marked [AGENT-INTRODUCED]",
    "Validate cycles: all launched cycles judged",
    "Chosen option Grilled (≥1 stress-test entry per major branch)",
    "Open questions all marked [TBD] / [BLOCKED] / [?] (none silent)",
    "Quality gates specified (≥1 runnable command)",
    "Reproduction loop captured if Diagnose ran (or [BLOCKED] if no loop is possible)",
)

MODES: tuple[Node, ...] = (
    Node("explore", "Explore", "mode"),
    Node("ground", "Ground", "mode"),
    Node("shape", "Shape", "mode"),
    Node("sketch", "Sketch", "mode"),
    Node("grill", "Grill", "mode"),
    Node("diagnose", "Diagnose", "mode"),
)

HANDSHAKE = Node("handshake", "Two-key handshake", "handshake")
CURDLE = Node("curdle", "Curdle (extract spec)", "terminal")


def _build_model() -> GateModel:
    gates = tuple(_gate(label) for label in COHERENCE_GATES)
    nodes = (*MODES, *gates, HANDSHAKE, CURDLE)
    edges = (
        Edge("explore", "ground"),
        Edge("ground", "shape"),
        Edge("shape", "sketch"),
        Edge("sketch", "grill"),
        Edge("diagnose", "shape"),
        # every gate feeds the handshake; the handshake unlocks curdle.
        *(Edge(g.id, "handshake") for g in gates),
        Edge("grill", "handshake"),
        Edge("handshake", "curdle", "both keys"),
    )
    return GateModel(nodes=nodes, edges=edges)


GATE_MODEL = _build_model()


def coherence_checklist() -> tuple[str, ...]:
    """The checklist labels the model is built from — the rigor-parity anchor."""
    return COHERENCE_GATES


def _dot_id(node_id: str) -> str:
    return node_id.replace("-", "_")


def to_dot(model: GateModel = GATE_MODEL) -> str:
    """Canonical Graphviz document. Deterministic node/edge order for byte-stable
    snapshots."""
    lines = ["digraph mold_gates {", "  rankdir=LR;", '  node [shape=box];']
    for node in model.nodes:
        label = node.label.replace('"', '\\"')
        lines.append(f'  {_dot_id(node.id)} [label="{label}", kind="{node.kind}"];')
    for edge in model.edges:
        attr = f' [label="{edge.label}"]' if edge.label else ""
        lines.append(f"  {_dot_id(edge.src)} -> {_dot_id(edge.dst)}{attr};")
    lines.append("}")
    return "\n".join(lines) + "\n"


def to_mermaid(model: GateModel = GATE_MODEL) -> str:
    """The same model as a Mermaid flowchart — renders natively in markdown
    viewers, no Graphviz binary required."""
    lines = ["```mermaid", "flowchart LR"]
    for node in model.nodes:
        label = (
            node.label.replace('"', "'")
            .replace("[", "&#91;")
            .replace("]", "&#93;")
        )
        lines.append(f'  {_dot_id(node.id)}["{label}"]')
    for edge in model.edges:
        arrow = f"-- {edge.label} -->" if edge.label else "-->"
        lines.append(f"  {_dot_id(edge.src)} {arrow} {_dot_id(edge.dst)}")
    lines.append("```")
    return "\n".join(lines) + "\n"


def dot_available() -> bool:
    return shutil.which("dot") is not None


class RenderError(Exception):
    pass


def render(
    target: str,
    model: GateModel = GATE_MODEL,
    *,
    dot_present: bool | None = None,
) -> tuple[str, bytes]:
    """Render the model for ``target``.

    Returns ``(effective_target, payload_bytes)``. ``svg``/``png`` shell out to
    Graphviz ``dot``; when ``dot`` is absent they degrade to a mermaid block and
    the returned effective target is ``"mermaid"`` so the caller can name the
    fallback. ``dot`` (text) and ``mermaid`` never need the binary.
    """
    if target not in RENDER_TARGETS:
        raise RenderError(f"unknown render target: {target!r}; choose from {', '.join(RENDER_TARGETS)}")
    have_dot = dot_available() if dot_present is None else dot_present

    if target == "mermaid":
        return "mermaid", to_mermaid(model).encode("utf-8")
    if target == "dot":
        return "dot", to_dot(model).encode("utf-8")
    # svg / png — need the binary, else degrade to mermaid.
    if not have_dot:
        return "mermaid", to_mermaid(model).encode("utf-8")
    try:
        proc = subprocess.run(
            ["dot", f"-T{target}"],
            input=to_dot(model).encode("utf-8"),
            capture_output=True,
            timeout=30,
        )
    except subprocess.TimeoutExpired:
        raise RenderError(f"dot -T{target} timed out after 30 s")
    if proc.returncode != 0:
        raise RenderError(f"dot -T{target} failed: {proc.stderr.decode('utf-8', 'replace').strip()}")
    return target, proc.stdout


def _load_state(path: Path) -> dict:
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise RenderError(f"could not read state file {path}: {exc}") from exc
    if not isinstance(obj, dict):
        raise RenderError(
            f"state file {path} must be a JSON object, got {type(obj).__name__}"
        )
    return obj


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument(
        "--state",
        type=Path,
        help="Optional mold state.json (reserved for per-session annotation; "
        "the gate model itself is static).",
    )
    parser.add_argument(
        "--render",
        choices=RENDER_TARGETS,
        default="dot",
        help="Render target. svg/png need Graphviz `dot`; absent it degrades to mermaid.",
    )
    parser.add_argument(
        "--out",
        type=Path,
        help="Write to this path instead of stdout (required when the effective "
        "output is binary — svg/png with Graphviz present).",
    )
    args = parser.parse_args(argv)

    if args.state is not None:
        try:
            _load_state(args.state)  # validated for shape; model stays static
        except RenderError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2

    try:
        effective, payload = render(args.render)
    except RenderError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if effective != args.render:
        print(
            f"note: `dot` not on PATH; degraded {args.render} -> {effective}",
            file=sys.stderr,
        )

    if args.out is not None:
        try:
            args.out.write_bytes(payload)
        except OSError as exc:
            print(f"error: could not write {args.out}: {exc}", file=sys.stderr)
            return 2
        print(str(args.out))
        return 0

    if effective in BINARY_TARGETS:
        print(
            f"error: {effective} is binary; pass --out <path>",
            file=sys.stderr,
        )
        return 2
    sys.stdout.write(payload.decode("utf-8"))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
