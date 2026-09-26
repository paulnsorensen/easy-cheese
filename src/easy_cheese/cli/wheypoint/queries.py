"""The eight read-only commands: show, resolve, lint, validate, schema, list, log, turns."""

from __future__ import annotations

import datetime as _dt
import json
from collections.abc import Callable
from pathlib import Path
from typing import Literal, TextIO, cast

import fromargs

from easy_cheese_schemas import CheckpointIntent, load
from easy_cheese_schemas import schema_runtime

from easy_cheese.shared import paths
from easy_cheese.shared.wheypoint import checkpoint as checkpoint_mod
from easy_cheese.shared.wheypoint import discovery
from easy_cheese.shared.wheypoint import lint as lint_mod
from easy_cheese.shared.wheypoint import projection
from easy_cheese.shared.wheypoint import records
from easy_cheese.shared.wheypoint import resolve as resolve_mod
from easy_cheese.shared.wheypoint import resolve_cli
from easy_cheese.shared.wheypoint import storage
from easy_cheese.shared.wheypoint import transcript as transcript_mod
from easy_cheese.shared.wheypoint.resolve_cli import findings_payload, maybe_payload

from easy_cheese.cli.wheypoint.checkpoint import open_store, read_intent


def _project_key(value: str) -> str:
    """Reject anything that is not one filesystem path segment (G9, G10)."""
    if not value or value in (".", "..") or "/" in value or "\\" in value:
        raise fromargs.CliError(f"--project: must be one path segment, not {value!r}")
    return value


def _iso_date(value: str) -> str:
    """Accept only a `YYYY-MM-DD` date, so a bad `--since` is a usage error."""
    try:
        _ = _dt.date.fromisoformat(value)
    except ValueError as exc:
        raise fromargs.CliError(
            f"--since: must be a YYYY-MM-DD date, not {value!r}"
        ) from exc
    return value


def _positive_int(value: int) -> int:
    """Accept only a whole number of at least 1 for `--limit`."""
    if value < 1:
        raise fromargs.CliError(f"--limit: must be at least 1, not {value}")
    return value


def run_show(work_id: str, *, project: str | None = None) -> dict[str, object]:
    project_key = _project_key(project) if project is not None else None
    corpus_root = None if project_key is None else paths.corpus_home() / project_key
    store = open_store(work_id, corpus_root=corpus_root)
    try:
        record = store.read_record()
    except (storage.StorageError, OSError, ValueError) as exc:
        raise fromargs.CliError(f"record-unreadable: {exc}", exit_code=1) from exc
    if record is None:
        raise fromargs.CliError(
            f"record-missing: work {work_id!r} has no record at {store.record_path}",
            exit_code=1,
        )
    return {
        "work_id": record.work_id,
        "status": record.status.value,
        "revision_id": record.revision_id,
        "revision_number": record.revision_number,
        "record": records.unstructure(record),
    }


def run_resolve(
    ref: str,
    *,
    legacy: bool = False,
    corpus_root: str | None = None,
    project: str | None = None,
    workspace_root: str | None = None,
) -> dict[str, object]:
    # A legacy note lives beside the repository, not in a corpus, so a
    # corpus root given with --legacy would be silently dropped.
    chosen = [
        name
        for name, value in (("--legacy", legacy), ("--corpus-root", corpus_root), ("--project", project))
        if value
    ]
    if len(chosen) > 1:
        raise fromargs.CliError(f"{chosen[0]}: not allowed with {chosen[1]}")
    project_key = _project_key(project) if project is not None else None
    corpus_root_path = None if project_key is None else paths.corpus_home() / project_key
    effective_corpus_root = str(corpus_root_path) if corpus_root_path is not None else corpus_root
    resolution = (
        resolve_mod.resolve_legacy(ref, start=Path.cwd())
        if legacy
        else resolve_mod.resolve(
            ref,
            corpus_root=effective_corpus_root,
            project_key=project_key,
            workspace_root=workspace_root,
            require_workspace=project_key is not None,
        )
    )
    payload = resolve_cli.resolve_payload(resolution, ref)
    if resolution.outcome == resolve_mod.ResolutionOutcome.NOT_FOUND:
        payload["suggestions"] = list(
            discovery.suggestions(ref, start=Path.cwd(), corpus_root=effective_corpus_root)
        )
    resolve_cli.raise_if_error(payload)
    return payload


def run_lint(path: str) -> dict[str, object]:
    report = lint_mod.lint_projection_file(path)
    return {
        "path": path,
        "clean": report.ok,
        "findings": findings_payload(report.findings),
        "projection": maybe_payload(report.projection),
    }


def run_validate(intent: str | None, stdin: TextIO) -> dict[str, object]:
    """Schema-only dry run: every problem, no store opened (AC-11)."""
    payload = read_intent(intent, stdin)
    if not isinstance(payload, dict):
        raise fromargs.CliError(
            "invalid-intent: a checkpoint intent must be a JSON object, not "
            + f"{type(payload).__name__}",
            exit_code=1,
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
        raise fromargs.CliError("invalid-intent: " + "; ".join(problems), exit_code=1)
    return {"valid": True, "work_id": loaded.value.work_id if loaded.value else None}


def run_schema(slug: str) -> dict[str, object]:
    """The JSON Schema for one registered contract, so no one unzips the bundle (AC-12)."""
    table = dict(schema_runtime.contract_registry())
    if slug not in table:
        raise fromargs.CliError(
            f"unknown-contract: no contract is registered as {slug!r}; known: "
            + f"{', '.join(sorted(table))}",
            exit_code=1,
        )
    document = cast(
        dict[str, object], json.loads(schema_runtime.schema_bytes(table[slug]))
    )
    return {"slug": slug, "schema": document}


def _iso(epoch: float) -> str:
    return _dt.datetime.fromtimestamp(epoch, tz=_dt.timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )


def _hit_item(hit: discovery.Hit) -> dict[str, object]:
    """A discovery hit as a `list` item: the old store keys, plus G9's new ones."""
    item: dict[str, object] = {
        "source": hit.source,
        "project": hit.project,
        "ref": hit.ref,
        "status": hit.status,
        "next": hit.next,
        "orientation": hit.orientation,
        "path": str(hit.path),
        "resume": str(hit.resume),
        "updated": _iso(hit.updated),
    }
    if hit.source == "store":
        item["work_id"] = hit.ref
        item["revision_number"] = hit.revision_number
    if hit.problem is not None:
        item["problem"] = hit.problem
    return item


def _tsv_lines(
    items: list[dict[str, object]],
    columns: tuple[str | tuple[str, Callable[[object], str]], ...],
) -> list[str]:
    """One tab-separated line per item; a missing or null cell renders as `-`."""
    lines: list[str] = []
    for item in items:
        cells: list[str] = []
        for column in columns:
            key, formatter = column if isinstance(column, tuple) else (column, str)
            value = item.get(key)
            cell = "-" if value is None else formatter(value)
            cells.append(projection.escape(cell, tab=True))
        lines.append("\t".join(cells))
    return lines


def run_list(
    *,
    corpus_root: str | None = None,
    scope: Literal["project", "machine"] = "project",
    project: list[str] | None = None,
    root: list[str] | None = None,
    grep: list[str] | None = None,
    status: list[str] | None = None,
    next: list[str] | None = None,
    source: Literal["store", "note"] | None = None,
    since: str | None = None,
    limit: int | None = None,
    mirrors: bool = False,
) -> dict[str, object]:
    """Every store and legacy note a caller can resume from (AC-13, G9)."""
    root_arg = Path(corpus_root) if corpus_root is not None else paths.project_corpus_root()
    projects = [_project_key(key) for key in (project or [])]
    if since is not None:
        since = _iso_date(since)
    if limit is not None:
        limit = _positive_int(limit)
    effective_scope = "machine" if projects else scope
    result = discovery.discover(
        scope=effective_scope,
        start=Path.cwd(),
        corpus_root=corpus_root,
        projects=projects,
        roots=root or [],
        grep=grep or (),
        status=status or (),
        next=next or (),
        source=source,
        since=since,
        limit=limit,
        show_mirrors=mirrors,
    )
    items = [_hit_item(hit) for hit in result.hits]
    lines = _tsv_lines(
        items, ("source", "project", "ref", "status", "next", "orientation")
    )
    return {
        "corpus_root": str(root_arg),
        "scope": effective_scope,
        "items": items,
        "lines": lines,
        "searched": list(result.searched),
        "hidden_mirrors": result.hidden_mirrors,
        "errors": list(result.errors),
    }


def run_log(
    work_id: str, *, corpus_root: str | None = None, project: str | None = None
) -> dict[str, object]:
    """One line per complete revision, oldest first (AC-14)."""
    project_key = _project_key(project) if project is not None else None
    root = None if project_key is None else paths.corpus_home() / project_key
    if root is None:
        root = Path(corpus_root) if corpus_root is not None else paths.project_corpus_root()
    store = open_store(work_id, corpus_root=root)
    scan = store.revisions()
    files, skipped = scan.files, scan.skipped
    if not files:
        try:
            record = store.read_record()
        except (storage.StorageError, OSError, ValueError) as exc:
            raise fromargs.CliError(f"record-unreadable: {exc}", exit_code=1) from exc
        if record is None:
            raise fromargs.CliError(
                f"record-missing: work {work_id!r} has no record at "
                + f"{store.record_path}",
                exit_code=1,
            )
        raise fromargs.CliError(
            f"store-inconsistent: work {work_id!r} has a record but no complete "
            + "revisions"
            + (f": {'; '.join(skipped)}" if skipped else ""),
            exit_code=1,
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


def run_turns(
    *, transcript: str | None = None, session: str | None = None
) -> dict[str, object]:
    """The user's own turns from a session transcript (AC-27, AC-28)."""
    if transcript is not None:
        path = Path(transcript)
    else:
        directory = transcript_mod.projects_dir(Path.cwd())
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
            candidates_text = (
                ", ".join(
                    f"{item['session']} (modified {item['modified'] or 'unknown'})"
                    for item in listing
                )
                or "none"
            )
            raise fromargs.CliError(
                f"session-required: {len(listing)} transcript(s) under {directory}: "
                + "pass --session <id> (never guessed by recency) or --transcript "
                + f"<path>. projects_dir: {directory}. candidates: {candidates_text}",
                exit_code=1,
            )
        if transcript_mod.SESSION_ID_RE.fullmatch(session) is None:
            raise fromargs.CliError(
                f"invalid-session: session id {session!r} must be one safe "
                + "file-name segment",
                exit_code=1,
            )
        path = directory / f"{session}.jsonl"
    if not path.is_file():
        raise fromargs.CliError(f"transcript-missing: no transcript at {path}", exit_code=1)
    turns, skipped = transcript_mod.user_turns(path)
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