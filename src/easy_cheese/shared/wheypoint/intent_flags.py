"""Checkpoint flags, overlaid onto the intent payload a file would carry.

A flag form and the equivalent hand-written intent must commit the same
revision, so this module builds the file form's JSON and nothing else: the
caller structures it into a `CheckpointIntent` exactly as it structures a file.

The overlay is pure and deterministic. Payload items come first; flag items
follow in the order of the keyword parameters. A scalar flag (`work_id`,
`orientation`, `next`, `artifact`, `notes`) overrides the payload's value
without a refusal, because the flag is the later, more specific statement.

Rationales pair in one sequence: gated questions (`--gates`) take the first
ones, then the decisions, then each `resolve`, then each `withdraw`, then each
`supersede`. A `supersede` names its successor with `by`; with no `by`, the
successor is the one entry of the superseded entry's kind that the checkpoint
adds. A gating
question needs a rationale; a plain question takes none.
"""

from __future__ import annotations

import copy
import re
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import cast

from easy_cheese_schemas.contracts import EdgeKind

from . import commit, ref_grammar

__all__ = ["UNPINNED_LINE_REF", "IntentFlagError", "overlay", "pin_line_refs"]

UNPINNED_LINE_REF = "unpinned-line-ref"


class IntentFlagError(ValueError):
    """Flags that do not describe one intent; the message starts with a code."""


def overlay(
    payload: Mapping[str, object] | None,
    *,
    work_id: str | None = None,
    question: Sequence[str] = (),
    gates: bool = False,
    decision: Sequence[str] = (),
    rationale: Sequence[str] = (),
    directive: Sequence[str] = (),
    quote: Sequence[str] = (),
    resolve: Sequence[str] = (),
    withdraw: Sequence[str] = (),
    supersede: Sequence[str] = (),
    by: Sequence[str] = (),
    owner: Sequence[str] = (),
    when: Sequence[str] = (),
    operator_directive: Sequence[str] = (),
    operator_quote: Sequence[str] = (),
    orientation: str | None = None,
    next: str | None = None,
    artifact: str | None = None,
    context: Sequence[str] = (),
    notes: str | None = None,
    link: Sequence[str] = (),
    kind: Sequence[str] = (),
    covers: Sequence[str] = (),
    base: str | None = None,
) -> dict[str, object]:
    """`payload` (an intent file's JSON, or `{}`) with the flags applied.

    `owner` and `when` pair by position with `question`. `quote` pairs by
    position with `directive`, and `operator_quote` with `operator_directive`.
    """
    _check_pairing(
        owner=owner,
        when=when,
        operator_directive=operator_directive,
        operator_quote=operator_quote,
        supersede=supersede,
        by=by,
        question=question,
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
    gated = len(question) if gates else 0
    result: dict[str, object] = copy.deepcopy(dict(payload or {}))
    scalars = {
        "work_id": work_id,
        "orientation": orientation,
        "next": next,
        "artifact": artifact,
        "notes": notes,
        "base_revision_id": base,
    }
    result.update({key: value for key, value in scalars.items() if value is not None})
    _extend(result, "working_context", list(context))

    question_rationales = rationale[:gated]
    rest = rationale[gated:]
    decision_rationales = rest[: len(decision)]
    resolve_rationales = rest[len(decision) : len(decision) + len(resolve)]
    withdraw_end = len(decision) + len(resolve) + len(withdraw)
    withdraw_rationales = rest[len(decision) + len(resolve) : withdraw_end]
    supersede_rationales = rest[withdraw_end:]
    _extend(
        result,
        "entries",
        [
            *_questions(question, gates, question_rationales, owner, when),
            *(
                {"kind": "decision", "summary": text, "rationale": why}
                for text, why in zip(decision, decision_rationales, strict=True)
            ),
            *(
                {"kind": "directive", "summary": text, "quote": words}
                for text, words in zip(directive, quote, strict=True)
            ),
            *(
                {"kind": "directive", "summary": text, "quote": words, "scope": "operator"}
                for text, words in zip(
                    operator_directive, operator_quote, strict=True
                )
            ),
        ],
    )
    _extend(
        result,
        "transitions",
        [
            *_transitions("resolve", resolve, resolve_rationales),
            *_transitions("withdraw", withdraw, withdraw_rationales),
            *_supersessions(result, supersede, by, supersede_rationales),
        ],
    )
    edges, links = _links(link, kind, covers)
    _extend(result, "add_edges", edges)
    _extend(result, "artifact_links", links)
    return result


def pin_line_refs(
    payload: Mapping[str, object],
    *,
    checkout: Path | None,
    head: str | None,
) -> tuple[dict[str, object], list[str]]:
    """`payload` with each bare `path:line` pinned to `head`, and the warnings.

    Only `working_context` items and `artifact_links` are read. A token pins
    when it names an existing file in `checkout`; `path#symbol` and an already
    pinned token stay as written. With no checkout or no `head`, a token that
    looks like `path:line` stays unpinned and the warning `unpinned-line-ref`
    names it once. The pin is made at checkpoint and never on read.
    """
    result: dict[str, object] = copy.deepcopy(dict(payload))
    unpinned = False

    def pin(text: str) -> str:
        def swap(match: re.Match[str]) -> str:
            nonlocal unpinned
            if checkout is None or head is None:
                unpinned = True
                return match.group(0)
            if not _is_checkout_file(checkout, match["path"]):
                return match.group(0)
            return f"{match['path']}:{match['line']}@{head}"

        return ref_grammar.LINE_REF_RE.sub(swap, text)

    context = result.get("working_context")
    if isinstance(context, list):
        result["working_context"] = [
            pin(item) if isinstance(item, str) else item
            for item in cast(list[object], context)
        ]
    links = result.get("artifact_links")
    if isinstance(links, list):
        result["artifact_links"] = [
            _pin_link(cast(Mapping[str, object], item), pin)
            if isinstance(item, Mapping)
            else item
            for item in cast(list[object], links)
        ]
    return result, [UNPINNED_LINE_REF] if unpinned else []


def _pin_link(
    link: Mapping[str, object], pin: Callable[[str], str]
) -> dict[str, object]:
    """A copy of `link` whose `path` and `repo:` ref are pinned."""
    pinned = dict(link)
    path = pinned.get("path")
    if isinstance(path, str):
        pinned["path"] = pin(path)
    ref = pinned.get("ref")
    if isinstance(ref, str) and ref.startswith("repo:"):
        pinned["ref"] = "repo:" + pin(ref[len("repo:") :])
    return pinned


def _is_checkout_file(checkout: Path, relative: str) -> bool:
    try:
        resolved = (checkout / relative).resolve()
        return resolved.is_file() and resolved.is_relative_to(checkout.resolve())
    except (OSError, RuntimeError):
        return False


def _check_pairing(
    *,
    owner: Sequence[str],
    when: Sequence[str],
    operator_directive: Sequence[str],
    operator_quote: Sequence[str],
    supersede: Sequence[str],
    by: Sequence[str],
    question: Sequence[str],
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
    wanted = (len(question) if gates else 0) + len(decision) + len(resolve)
    wanted += len(withdraw) + len(supersede)
    if by and len(by) != len(supersede):
        raise IntentFlagError(
            f"flag-pairing: {len(by)} --by for {len(supersede)} --supersede"
        )
    if len(rationale) != wanted:
        raise IntentFlagError(
            f"flag-pairing: {len(rationale)} --rationale for {wanted} "
            + "--gates --question, --decision, --resolve, --withdraw, and --supersede flags"
        )
    for flag, values in (("--owner", owner), ("--when", when)):
        if values and len(values) != len(question):
            raise IntentFlagError(
                f"flag-pairing: {len(values)} {flag} for {len(question)} --question"
            )
    for flag, quotes, directives, directive_flag in (
        ("--quote", quote, directive, "--directive"),
        ("--operator-quote", operator_quote, operator_directive, "--operator-directive"),
    ):
        if len(quotes) != len(directives):
            raise IntentFlagError(
                f"flag-pairing: {len(quotes)} {flag} for {len(directives)} {directive_flag}"
            )
    if len(kind) != len(link):
        raise IntentFlagError(
            f"flag-pairing: {len(kind)} --kind for {len(link)} --link"
        )
    if gates and not question:
        raise IntentFlagError("flag-pairing: --gates needs --question")


def _questions(
    questions: Sequence[str],
    gates: bool,
    rationales: Sequence[str],
    owners: Sequence[str],
    whens: Sequence[str],
) -> list[dict[str, object]]:
    items: list[dict[str, object]] = []
    for index, text in enumerate(questions):
        item: dict[str, object] = {
            "kind": "question",
            "summary": text,
            "blocks_continuation": gates,
        }
        if gates:
            item["rationale"] = rationales[index]
        if owners:
            item["owner"] = owners[index]
        if whens:
            item["when"] = whens[index]
        items.append(item)
    return items


def _transitions(
    action: str, entry_ids: Sequence[str], rationales: Sequence[str]
) -> list[dict[str, object]]:
    return [
        {"entry_id": entry_id, "action": action, "rationale": why}
        for entry_id, why in zip(entry_ids, rationales, strict=True)
    ]


def _supersessions(
    result: Mapping[str, object],
    superseded: Sequence[str],
    by: Sequence[str],
    rationales: Sequence[str],
) -> list[dict[str, object]]:
    """A supersede transition per `--supersede`, each with its successor."""
    return [
        {
            "entry_id": entry_id,
            "action": "supersede",
            "rationale": why,
            "target_entry_id": by[index] if by else _lone_successor(result, entry_id),
        }
        for index, (entry_id, why) in enumerate(zip(superseded, rationales, strict=True))
    ]


def _lone_successor(result: Mapping[str, object], entry_id: str) -> str:
    """The id of the one entry of `entry_id`'s kind that the checkpoint adds.

    Added entries take ids from the parent revision, so the base must be known.
    """
    kind = commit.kind_of_entry_id(entry_id)
    if kind is None:
        raise IntentFlagError(
            f"flag-pairing: --supersede {entry_id} has no --by and its id prefix "
            + "names no entry kind"
        )
    entries = result.get("entries")
    proposals = [
        cast(Mapping[str, object], item)
        for item in (cast(list[object], entries) if isinstance(entries, list) else [])
        if isinstance(item, Mapping)
        and cast(Mapping[str, object], item).get("kind") == kind.value
    ]
    if len(proposals) != 1:
        raise IntentFlagError(
            f"flag-pairing: --supersede {entry_id} has no --by and the checkpoint "
            + f"does not add exactly one entry of its kind (found {len(proposals)})"
        )
    work_id, base = result.get("work_id"), result.get("base_revision_id")
    if not isinstance(work_id, str) or not isinstance(base, str):
        raise IntentFlagError(
            f"flag-pairing: --supersede {entry_id} has no --by, so the successor's "
            + "id needs the work id and --base"
        )
    proposal = proposals[0]
    return commit.proposed_entry_id(
        work_id,
        base,
        kind,
        str(proposal["summary"]),
        bool(proposal.get("blocks_continuation", False)),
        0,
    )


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
