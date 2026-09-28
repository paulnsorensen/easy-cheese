"""Checkpoint flags, overlaid onto the intent payload a file would carry.

A flag form and the equivalent hand-written intent must commit the same
revision, so this module builds the file form's JSON and nothing else: the
caller structures it into a `CheckpointIntent` exactly as it structures a file.

The overlay is pure and deterministic. Payload items come first; flag items
follow in the order of the keyword parameters. A scalar flag (`work_id`,
`orientation`, `next`, `artifact`, `notes`) overrides the payload's value
without a refusal, because the flag is the later, more specific statement.

Rationales pair in one sequence: the decisions take the first ones, then each
`resolve`, then each `withdraw`.
"""

from __future__ import annotations

import copy
from collections.abc import Mapping, Sequence
from typing import cast

from easy_cheese_schemas.contracts import EdgeKind

from . import ref_grammar

__all__ = ["IntentFlagError", "overlay"]


class IntentFlagError(ValueError):
    """Flags that do not describe one intent; the message starts with a code."""


def overlay(
    payload: Mapping[str, object] | None,
    *,
    work_id: str | None = None,
    question: Sequence[str] = (),
    blocker: Sequence[str] = (),
    gates: bool = False,
    decision: Sequence[str] = (),
    rationale: Sequence[str] = (),
    directive: Sequence[str] = (),
    quote: Sequence[str] = (),
    resolve: Sequence[str] = (),
    withdraw: Sequence[str] = (),
    orientation: str | None = None,
    next: str | None = None,
    artifact: str | None = None,
    context: Sequence[str] = (),
    notes: str | None = None,
    link: Sequence[str] = (),
    kind: Sequence[str] = (),
    covers: Sequence[str] = (),
) -> dict[str, object]:
    """`payload` (an intent file's JSON, or `{}`) with the flags applied."""
    _check_pairing(
        question=question,
        blocker=blocker,
        gates=gates,
        decision=decision,
        rationale=rationale,
        directive=directive,
        quote=quote,
        resolve=resolve,
        withdraw=withdraw,
        link=link,
        kind=kind,
    )
    result: dict[str, object] = copy.deepcopy(dict(payload or {}))
    scalars = {
        "work_id": work_id,
        "orientation": orientation,
        "next": next,
        "artifact": artifact,
        "notes": notes,
    }
    result.update({key: value for key, value in scalars.items() if value is not None})
    _extend(result, "working_context", list(context))

    decision_rationales = rationale[: len(decision)]
    resolve_rationales = rationale[len(decision) : len(decision) + len(resolve)]
    withdraw_rationales = rationale[len(decision) + len(resolve) :]
    _extend(
        result,
        "entries",
        [
            *(_gate("question", text, gates) for text in question),
            *(_gate("blocker", text, gates) for text in blocker),
            *(
                {"kind": "decision", "summary": text, "rationale": why}
                for text, why in zip(decision, decision_rationales, strict=True)
            ),
            *(
                {"kind": "directive", "summary": text, "quote": words}
                for text, words in zip(directive, quote, strict=True)
            ),
        ],
    )
    _extend(
        result,
        "transitions",
        [
            *_transitions("resolve", resolve, resolve_rationales),
            *_transitions("withdraw", withdraw, withdraw_rationales),
        ],
    )
    edges, links = _links(link, kind, covers)
    _extend(result, "add_edges", edges)
    _extend(result, "artifact_links", links)
    return result


def _check_pairing(
    *,
    question: Sequence[str],
    blocker: Sequence[str],
    gates: bool,
    decision: Sequence[str],
    rationale: Sequence[str],
    directive: Sequence[str],
    quote: Sequence[str],
    resolve: Sequence[str],
    withdraw: Sequence[str],
    link: Sequence[str],
    kind: Sequence[str],
) -> None:
    wanted = len(decision) + len(resolve) + len(withdraw)
    if len(rationale) != wanted:
        raise IntentFlagError(
            f"flag-pairing: {len(rationale)} --rationale for {wanted} "
            + "--decision, --resolve, and --withdraw flags"
        )
    if len(quote) != len(directive):
        raise IntentFlagError(
            f"flag-pairing: {len(quote)} --quote for {len(directive)} --directive"
        )
    if len(kind) != len(link):
        raise IntentFlagError(
            f"flag-pairing: {len(kind)} --kind for {len(link)} --link"
        )
    if gates and not (question or blocker):
        raise IntentFlagError("flag-pairing: --gates needs --question or --blocker")


def _gate(entry_kind: str, summary: str, gates: bool) -> dict[str, object]:
    return {"kind": entry_kind, "summary": summary, "blocks_continuation": gates}


def _transitions(
    action: str, entry_ids: Sequence[str], rationales: Sequence[str]
) -> list[dict[str, object]]:
    return [
        {"entry_id": entry_id, "action": action, "rationale": why}
        for entry_id, why in zip(entry_ids, rationales, strict=True)
    ]


def _links(
    link: Sequence[str], kind: Sequence[str], covers: Sequence[str]
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    """The edge for each `--link`, and a pinned link for each pinnable one."""
    edges: list[dict[str, object]] = []
    links: list[dict[str, object]] = []
    for ref, edge_kind in zip(link, kind, strict=True):
        if edge_kind not in {item.value for item in EdgeKind}:
            known = ", ".join(item.value for item in EdgeKind)
            raise IntentFlagError(
                f"flag-kind: --kind {edge_kind!r} names none of {known}"
            )
        try:
            parsed = ref_grammar.parse_ref(ref)
        except ValueError as exc:
            raise IntentFlagError(f"flag-link: {exc}") from exc
        edges.append({"to": ref, "kind": edge_kind})
        if ref_grammar.is_pinnable(parsed.scheme):
            links.append(
                {
                    "path": ref.partition(":")[2],
                    "ref": ref,
                    "covers_entry_ids": list(covers),
                }
            )
    if covers and not links:
        raise IntentFlagError("flag-pairing: --covers needs a pinnable --link")
    return edges, links


def _extend(result: dict[str, object], key: str, items: Sequence[object]) -> None:
    """Append `items` to the payload's list at `key`, if there are any."""
    if not items:
        return
    carried = result.get(key)
    if carried is None:
        carried = []
    if not isinstance(carried, list):
        raise IntentFlagError(
            f"flag-conflict: the payload's {key} is not a list, so flags cannot extend it"
        )
    result[key] = [*cast(list[object], carried), *items]
