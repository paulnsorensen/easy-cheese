"""The eight read-only commands: show, resolve, lint, validate, schema, list, log, turns."""

from __future__ import annotations

import argparse
import datetime as _dt
import json
from collections.abc import Callable
from pathlib import Path
from typing import TextIO, cast

from easy_cheese_schemas import CheckpointIntent, load
from easy_cheese_schemas import schema_runtime

from easy_cheese.cli.envelope import Refused
from easy_cheese.shared import paths
from easy_cheese.shared.wheypoint import checkpoint as checkpoint_mod
from easy_cheese.shared.wheypoint import lint as lint_mod
from easy_cheese.shared.wheypoint import projection
from easy_cheese.shared.wheypoint import records
from easy_cheese.shared.wheypoint import resolve as resolve_mod
from easy_cheese.shared.wheypoint import resolve_cli
from easy_cheese.shared.wheypoint import storage
from easy_cheese.shared.wheypoint import transcript
from easy_cheese.shared.wheypoint.resolve_cli import findings_payload, maybe_payload

from easy_cheese.cli.wheypoint.checkpoint import open_store, read_payload


def run_show(args: argparse.Namespace, _stdin: TextIO) -> dict[str, object]:
    work_id = cast(str, args.work_id)
    store = open_store(work_id)
    try:
        record = store.read_record()
    except (storage.StorageError, OSError, ValueError) as exc:
        raise Refused("record-unreadable", str(exc)) from exc
    if record is None:
        raise Refused(
            "record-missing",
            f"work {work_id!r} has no record at {store.record_path}",
        )
    return {
        "work_id": record.work_id,
        "status": record.status.value,
        "revision_id": record.revision_id,
        "revision_number": record.revision_number,
        "record": records.unstructure(record),
    }


def run_resolve(args: argparse.Namespace, _stdin: TextIO) -> dict[str, object]:
    ref = cast(str, args.ref)
    legacy_flag = cast(bool, args.legacy)
    corpus_root = cast("str | None", args.corpus_root)
    resolution = (
        resolve_mod.resolve_legacy(ref, start=Path.cwd())
        if legacy_flag
        else resolve_mod.resolve(ref, corpus_root=corpus_root)
    )
    return resolve_cli.resolve_payload(resolution, ref)


def run_lint(args: argparse.Namespace, _stdin: TextIO) -> dict[str, object]:
    path = cast(str, args.path)
    report = lint_mod.lint_projection_file(path)
    return {
        "path": path,
        "clean": report.ok,
        "findings": findings_payload(report.findings),
        "projection": maybe_payload(report.projection),
    }


def run_validate(args: argparse.Namespace, stdin: TextIO) -> dict[str, object]:
    """Schema-only dry run: every problem, no store opened (AC-11)."""
    _ = args
    payload = read_payload(stdin)
    if not isinstance(payload, dict):
        raise Refused(
            "invalid-intent",
            f"a checkpoint intent must be a JSON object, not {type(payload).__name__}",
        )
    intent_payload = cast("dict[str, object]", payload)
    problems = [
        f"{name} belongs to the compaction proof or the parent binding: pass it "
        + "through --compacted or let the runtime bind it"
        for name in checkpoint_mod.commit_only_fields(intent_payload)
    ]
    scrubbed = {
        key: value
        for key, value in cast(dict[str, object], payload).items()
        if key not in checkpoint_mod.COMMIT_ONLY_FIELDS
    }
    loaded = load(scrubbed, CheckpointIntent, strict=True, forbid_unknown=True)
    problems.extend(loaded.problems)
    problems.extend(
        f"{hit} looks like a credential"
        for hit in checkpoint_mod.secret_fields(intent_payload)
    )
    action_intent = loaded.value
    if action_intent is None:
        # Invalid entries or unknown keys do not suppress independent action checks.
        action_fields = {
            "work_id",
            "next",
            "orientation",
            "artifact",
            "tasks",
            "parallel",
        }
        action_intent = load(
            {key: value for key, value in scrubbed.items() if key in action_fields},
            CheckpointIntent,
            strict=True,
            forbid_unknown=True,
        ).value
    if action_intent is not None:
        problems.extend(
            checkpoint_mod.delta_problems(action_intent, None, schema_only=True)
        )
    if problems:
        raise Refused("invalid-intent", "; ".join(problems), {"problems": problems})
    return {"valid": True, "work_id": loaded.value.work_id if loaded.value else None}


def run_schema(args: argparse.Namespace, _stdin: TextIO) -> dict[str, object]:
    """The JSON Schema for one registered contract, so no one unzips the bundle (AC-12)."""
    slug = cast(str, args.slug)
    table = dict(schema_runtime.contract_registry())
    if slug not in table:
        raise Refused(
            "unknown-contract",
            f"no contract is registered as {slug!r}; known: {', '.join(sorted(table))}",
            {"known": sorted(table)},
        )
    document = cast(
        dict[str, object], json.loads(schema_runtime.schema_bytes(table[slug]))
    )
    return {"slug": slug, "schema": document}


def _corpus_root(args: argparse.Namespace) -> Path:
    root_arg = cast("str | None", args.corpus_root)
    return Path(root_arg) if root_arg is not None else paths.project_corpus_root()


def _tsv_lines(
    items: list[dict[str, object]],
    columns: tuple[str | tuple[str, Callable[[object], str]], ...],
) -> list[str]:
    """One tab-separated line per item; a missing column key renders as `-`."""
    lines: list[str] = []
    for item in items:
        cells: list[str] = []
        for column in columns:
            key, formatter = column if isinstance(column, tuple) else (column, str)
            cell = "-" if key not in item else formatter(item[key])
            cells.append(projection.escape(cell, tab=True))
        lines.append("\t".join(cells))
    return lines


def run_list(args: argparse.Namespace, _stdin: TextIO) -> dict[str, object]:
    """One line per work item under the corpus root (AC-13)."""
    root = _corpus_root(args)
    items: list[dict[str, object]] = []
    for store in storage.WorkStore.enumerate(root):
        work_id = store.work_id
        try:
            record = store.read_record()
        except (storage.StorageError, records.RecordError, ValueError) as exc:
            items.append(
                {
                    "work_id": work_id,
                    "status": "unreadable",
                    "unreadable": str(exc),
                    "orientation": str(exc),
                }
            )
            continue
        if record is None:
            items.append({"work_id": work_id, "status": "no-record", "no_record": True})
            continue
        head = record.orientation.strip().partition("\n")[0]
        items.append(
            {
                "work_id": record.work_id,
                "revision_number": record.revision_number,
                "status": record.status.value,
                "next": record.next_action.move.value,
                "orientation": head,
            }
        )
    lines = _tsv_lines(
        items, ("work_id", "revision_number", "status", "next", "orientation")
    )
    return {"corpus_root": str(root), "items": items, "lines": lines}


def run_log(args: argparse.Namespace, _stdin: TextIO) -> dict[str, object]:
    """One line per complete revision, oldest first (AC-14)."""
    work_id = cast(str, args.work_id)
    store = open_store(work_id, corpus_root=_corpus_root(args))
    scan = store.revisions()
    files, skipped = scan.files, scan.skipped
    if not files:
        try:
            record = store.read_record()
        except (storage.StorageError, OSError, ValueError) as exc:
            raise Refused("record-unreadable", str(exc)) from exc
        if record is None:
            raise Refused(
                "record-missing",
                f"work {work_id!r} has no record at {store.record_path}",
            )
        raise Refused(
            "store-inconsistent",
            f"work {work_id!r} has a record but no complete revisions"
            + (f": {'; '.join(skipped)}" if skipped else ""),
        )
    entries: list[dict[str, object]] = []
    for file in files:
        revision = file.revision
        captured = (
            revision.session_provenance.captured_at
            if revision.session_provenance is not None
            and revision.session_provenance.captured_at is not None
            else "-"
        )
        entries.append(
            {
                "revision_number": revision.revision_number,
                "revision_id": revision.revision_id,
                "captured_at": captured,
                "additions": len(revision.applied_additions),
                "transitions": len(revision.applied_transitions),
                "compacted": revision.compaction is not None,
            }
        )
    lines = _tsv_lines(
        entries,
        (
            "revision_number",
            "revision_id",
            "captured_at",
            ("additions", lambda n: f"+{n}"),
            ("transitions", lambda n: f"~{n}"),
            ("compacted", lambda c: "compacted" if c else "-"),
        ),
    )
    unreadable = [
        {"path": path, "reason": reason}
        for path, _, reason in (entry.partition(": ") for entry in skipped)
    ]
    return {
        "work_id": work_id,
        "revisions": entries,
        "lines": lines,
        "unreadable": unreadable,
    }


def run_turns(args: argparse.Namespace, _stdin: TextIO) -> dict[str, object]:
    """The user's own turns from a session transcript (AC-27, AC-28)."""
    transcript_arg = cast("str | None", args.transcript)
    session = cast("str | None", args.session)
    if transcript_arg is not None:
        path = Path(transcript_arg)
    else:
        directory = transcript.projects_dir(Path.cwd())
        if session is None:
            stamped: list[tuple[float | None, str]] = []
            for candidate in directory.glob("*.jsonl"):
                try:
                    mtime: float | None = candidate.stat().st_mtime
                except OSError:
                    mtime = None
                stamped.append((mtime, candidate.stem))
            listing = [
                {
                    "session": stem,
                    "modified": (
                        None
                        if mtime is None
                        else _dt.datetime.fromtimestamp(
                            mtime, tz=_dt.timezone.utc
                        ).strftime(checkpoint_mod.TIMESTAMP_FORMAT)
                    ),
                }
                for mtime, stem in sorted(
                    stamped,
                    key=lambda pair: (pair[0] is not None, pair[0] or 0.0),
                    reverse=True,
                )
            ]
            raise Refused(
                "session-required",
                f"{len(listing)} transcript(s) under {directory}: pass --session <id> "
                + "(never guessed by recency) or --transcript <path>",
                {"projects_dir": str(directory), "candidates": listing},
            )
        if transcript.SESSION_ID_RE.fullmatch(session) is None:
            raise Refused(
                "invalid-session",
                f"session id {session!r} must be one safe file-name segment",
            )
        path = directory / f"{session}.jsonl"
    if not path.is_file():
        raise Refused(
            "transcript-missing", f"no transcript at {path}", {"path": str(path)}
        )
    turns, skipped = transcript.user_turns(path)
    rows: list[dict[str, object]] = [
        {"timestamp": turn["timestamp"], "text": turn["text"]} for turn in turns
    ]
    return {
        "transcript": str(path),
        "count": len(turns),
        "skipped_lines": skipped,
        "turns": rows,
        "lines": _tsv_lines(rows, ("timestamp", "text")),
    }
