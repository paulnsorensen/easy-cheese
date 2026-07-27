"""Write a handoff artifact (handoff preamble + optional body) atomically.

CLI:

    python3 shared/scripts/write_handoff_artifact.py \\
        --slug my-task --status ok --phase press --next age \\
        --artifact .cheese/cook/my-task.md \\
        --orientation "press hardened X" \\
        [--body-file path/to/body.md]

Writes ``.cheese/<phase>/<slug>.md`` containing the canonical preamble
(status / next / artifact / optional ``taste_test:`` and ``durable_flags:``
keyed lines / orientation) followed by an optional
body separated by a blank line. The write is atomic: contents land in a tmp
file inside the target directory and are then ``os.replace``'d into place
(atomic overwrite on POSIX and Windows alike), so readers never observe a
half-written file.

``--phase`` names *this* phase's own directory and is the on-disk path
authority. ``--next`` is preamble-content only — it tells the *next* phase
where the chain should go, but does not influence where this artifact lands.
For backward compatibility, ``--phase`` is optional: when omitted, the path
falls back to ``.cheese/<next>/<slug>.md`` (the legacy "write the next phase's
input" shape, kept so existing tests and callers do not break mid-rollout).
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import os
import sys
import tempfile
import uuid
from pathlib import Path

import cli
import handoff
import paths
import work


def _render_preamble(
    *,
    status: str,
    next_skill: str,
    artifact: str,
    orientation: str,
    taste_test: str | None = None,
    durable_flags: str | None = None,
    baseline: str | None = None,
) -> str:
    """Render the preamble via handoff.render_handoff_slug (single SSOT)."""
    # Parse status into (status_kind, halt_reason).
    if status.startswith("halt:"):
        halt_reason = status[len("halt:"):].strip()
        status_kind = "halt"
    else:
        halt_reason = None
        status_kind = status

    slug = handoff.HandoffSlug(
        status=status_kind,
        halt_reason=halt_reason,
        next_skill=next_skill,
        artifact=artifact or None,
        orientation=orientation,
        taste_test=taste_test,
        durable_flags=durable_flags,
        baseline=baseline,
    )
    return handoff.render_handoff_slug(slug)


def _reject_traversal(field: str, value: str) -> None:
    """Reject path-traversal segments in values used to build the on-disk path."""
    if ".." in value or "/" in value or "\\" in value:
        raise cli.CliError(f"{field} rejects path traversal: {value!r}")


def _build_contents(*, preamble: str, body: str | None) -> str:
    if body is None:
        return preamble + "\n"
    return preamble + "\n\n" + body


def write_artifact(
    *,
    slug: str,
    status: str,
    next_skill: str,
    artifact: str,
    orientation: str,
    body: str | None,
    root: Path,
    phase: str | None = None,
    taste_test: str | None = None,
    durable_flags: str | None = None,
    baseline: str | None = None,
) -> Path:
    """Write the artifact atomically; return the final path.

    The on-disk path is ``.cheese/<phase>/<slug>.md`` when ``phase`` is given;
    otherwise it falls back to ``.cheese/<next_skill>/<slug>.md`` (legacy).
    ``next_skill`` always lands in the preamble's ``next:`` field regardless,
    so callers can decouple "where this report lives" from "what runs next".
    """
    if not slug:
        raise cli.CliError("--slug must be non-empty")
    if not next_skill:
        raise cli.CliError("--next must be non-empty")
    if not orientation:
        raise cli.CliError("--orientation must be non-empty")
    _reject_traversal("--slug", slug)

    path_dir = phase if phase else next_skill
    cheese_root = (root / ".cheese").resolve()
    target = cheese_root / path_dir / f"{slug}.md"
    # Nested path_dir subdirs are allowed (factory chains write to subdirs); a
    # `..` or absolute escape out of .cheese/ is not.
    if cheese_root not in target.resolve().parents:
        raise cli.CliError(f"--phase/--next must stay under .cheese/: {path_dir!r}")
    target_dir = target.parent
    target_dir.mkdir(parents=True, exist_ok=True)

    preamble = _render_preamble(
        status=status,
        next_skill=next_skill,
        artifact=artifact,
        orientation=orientation,
        taste_test=taste_test,
        durable_flags=durable_flags,
        baseline=baseline,
    )
    contents = _build_contents(preamble=preamble, body=body)

    tmp = target.with_name(target.name + ".tmp")
    try:
        tmp.write_text(contents, encoding="utf-8")
        tmp.replace(target)
    except BaseException:
        # Atomic-rename contract: clean up the tmp on failure so callers never
        # see a half-written sibling. swallow tmp-cleanup errors — the real
        # failure is the one we're propagating.
        with contextlib.suppress(FileNotFoundError):
            tmp.unlink()
        raise
    return target




def _handoff_target(root: Path, phase: str, work_id: str, operation_id: str, slug: str) -> Path:
    if not phase or Path(phase).name != phase or phase in {".", ".."}:
        raise ValueError("invalid phase")
    work._validate_identifier(work_id, "work_id", "wk_")
    work._validate_identifier(operation_id, "operation_id", "op_")
    slug_error = paths.validate_slug(slug)
    if slug_error:
        raise ValueError(slug_error)
    base = (root.resolve() / ".cheese").resolve()
    target = (base / phase / work_id / f"{operation_id}-{slug}.md").resolve()
    if base not in target.parents:
        raise ValueError("invalid handoff target")
    return target


def _apply_patch(record: work.WorkRecord, attempt: work.WorkAttempt, patch: dict | None) -> None:
    """Compatibility wrapper around the WorkRecord-owned patch operation."""
    work.apply_work_patch(record, attempt, patch)


def _apply_handoff(record: work.WorkRecord, entry: dict, *, persist: bool = True) -> dict:
    envelope = handoff.HandoffEnvelope.from_mapping(entry["envelope"])
    contracts = entry.get("contracts")
    errors = handoff.validate_handoff(
        envelope, handoff.registry_from_mapping(contracts) if contracts is not None else None
    )
    if errors:
        raise ValueError("; ".join(errors))
    event = f"handoff:{envelope.operation_id}"
    if event in record.context_log:
        return {"work": record.to_mapping(), "artifact": envelope.artifact, "operation_id": envelope.operation_id}
    attempt = work._find_attempt(record, envelope.attempt_id)
    if attempt.status not in work.NONTERMINAL or attempt.current_phase not in {None, envelope.phase}:
        raise ValueError("handoff attempt is not active for its phase")
    task_id = entry.get("task_id")
    task = None
    if task_id is not None:
        task = next((item for item in record.tasks if item.get("task_id") == task_id), None)
        if (
            task is None
            or task.get("status") != "active"
            or task.get("attempt_id") != attempt.attempt_id
            or task.get("phase") != envelope.phase
        ):
            raise ValueError("task is not active for this attempt and phase")
    _apply_patch(record, attempt, entry.get("work_patch"))
    artifact = {"phase": envelope.phase, "operation_id": envelope.operation_id, "path": envelope.artifact}
    if artifact not in attempt.artifacts:
        attempt.artifacts.append(artifact)
    if envelope.status == "halt":
        pass
    elif envelope.next == "done":
        attempt.status = "completed"
    elif envelope.next == "hold":
        attempt.status = "paused"
    elif envelope.next == "tasks":
        for index, directive in enumerate(envelope.payload["tasks"]):
            directive_id = f"{envelope.operation_id}:{index}"
            if not any(item["task_id"] == directive_id for item in record.tasks):
                record.tasks.append({
                    "task_id": directive_id,
                    "phase": directive["phase"],
                    "subject": directive["subject"],
                    "input": directive.get("input", {}),
                    "status": "pending",
                    "attempt_id": None,
                    "reason": None,
                })
        attempt.status = "active"
    else:
        attempt.status = "active"
        attempt.current_phase = envelope.next
    if task is not None:
        task["status"] = "completed"
        task["reason"] = None
    record.context_log.append(event)
    work._derive_status(record)
    record.revision += 1
    if persist:
        work._save(record)
    return {"work": record.to_mapping(), "artifact": envelope.artifact, "operation_id": envelope.operation_id}


def _finish_prepared(entry: dict, record: work.WorkRecord) -> dict:
    target = Path(entry["target"])
    if not target.is_file():
        raise ValueError("prepared handoff artifact is missing")
    digest = hashlib.sha256(target.read_bytes()).hexdigest()
    if digest != entry.get("artifact_sha256"):
        raise ValueError("prepared handoff artifact does not match its journal")
    result = _apply_handoff(record, entry)
    entry["complete"] = True
    entry["result"] = result
    work._write_journal(Path(entry["journal"]), entry)
    return result


def _same_prepared_operation(existing: dict, proposed: dict) -> bool:
    fields = (
        "kind",
        "operation_id",
        "expected_revision",
        "target",
        "envelope",
        "work_patch",
        "task_id",
        "contracts",
        "artifact_sha256",
    )
    return all(existing.get(field) == proposed.get(field) for field in fields)


def _reconcile(entry: dict, record: work.WorkRecord) -> bool:
    if entry.get("kind") != "handoff" or entry.get("complete"):
        return False
    try:
        _finish_prepared(entry, record)
    except (OSError, ValueError):
        return False
    return True


work.register_reconciler("handoff", _reconcile)


def commit_handoff(
    phase: str,
    slug: str,
    work_id: str,
    attempt_id: str,
    expected_revision: int,
    next_phase: str,
    status: str,
    halt_reason: str | None,
    payload: dict,
    provenance: dict,
    work_patch: dict | None,
    body: str,
    task_id: str | None = None,
    operation_id: str | None = None,
    *,
    root: Path | str | None = None,
    project: str | None = None,
    contracts: handoff.TransitionRegistry | None = None,
) -> dict:
    """Commit an envelope artifact and its WorkRecord update as one journaled operation."""
    operation_id = operation_id or "op_" + uuid.uuid4().hex
    root_path = Path(root or Path.cwd())
    target = _handoff_target(root_path, phase, work_id, operation_id, slug)
    envelope = handoff.HandoffEnvelope(
        contract_version=handoff.CONTRACT_VERSION,
        work_id=work_id,
        attempt_id=attempt_id,
        operation_id=operation_id,
        phase=phase,
        status=status,
        halt_reason=halt_reason,
        next=next_phase,
        artifact=str(target),
        payload=payload,
        provenance=provenance,
    )
    errors = handoff.validate_handoff(envelope, contracts)
    if errors:
        raise ValueError("; ".join(errors))
    contents = handoff.render_handoff(envelope, body, contracts=contracts)
    artifact_sha256 = hashlib.sha256(contents.encode()).hexdigest()
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=target.parent, delete=False) as handle:
        handle.write(contents)
        temporary = Path(handle.name)
    record = work.load_work(work_id, project, include_local=False)
    try:
        with work.record_lock(record):
            record = work.load_work(work_id, project, include_local=False)
            record = work._recover_record_mutations(record)
            journal = work._journal_path(record, operation_id)
            proposed = {
                "kind": "handoff",
                "operation_id": operation_id,
                "expected_revision": expected_revision,
                "complete": False,
                "journal": str(journal),
                "target": str(target),
                "envelope": envelope.as_mapping(),
                "work_patch": work_patch,
                "task_id": task_id,
                "contracts": handoff.registry_as_mapping(contracts) if contracts is not None else None,
                "artifact_sha256": artifact_sha256,
            }
            if journal.is_file():
                entry = json.loads(journal.read_text(encoding="utf-8"))
                if not _same_prepared_operation(entry, proposed):
                    raise ValueError("operation_id reused with a different handoff")
                if entry.get("complete"):
                    return entry["result"]
                if not target.is_file():
                    os.replace(temporary, target)
                return _finish_prepared(entry, record)
            if record.revision != expected_revision:
                raise ValueError("stale work revision")
            if target.exists():
                raise ValueError("handoff target exists without an operation journal")
            preview = work._record_from_mapping(record.to_mapping())
            _apply_handoff(preview, proposed, persist=False)
            work._write_journal(journal, proposed)
            os.replace(temporary, target)
            return _finish_prepared(proposed, record)
    finally:
        with contextlib.suppress(FileNotFoundError):
            temporary.unlink()


def _run_json_request() -> None:
    try:
        request = json.load(sys.stdin)
        if not isinstance(request, dict):
            raise ValueError("request must be a JSON object")
        result = commit_handoff(**request)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        raise SystemExit(2) from exc
    print(json.dumps(result, default=str))


def _cmd_write(args: argparse.Namespace) -> None:
    body: str | None = None
    if args.body_file is not None:
        body_path = Path(args.body_file)
        if not body_path.is_file():
            raise cli.CliError(f"--body-file not found: {body_path}")
        body = body_path.read_text(encoding="utf-8")

    root = Path(args.root) if args.root else Path.cwd()
    target = write_artifact(
        slug=args.slug,
        status=args.status,
        next_skill=args.next,
        artifact=args.artifact,
        orientation=args.orientation,
        body=body,
        root=root,
        phase=args.phase,
        taste_test=args.taste_test,
        durable_flags=args.durable_flags,
        baseline=args.baseline,
    )
    cli.emit(str(target))


def _setup(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--slug", required=True, help="artifact slug (filename stem)")
    parser.add_argument("--status", required=True, help="'ok' or 'halt: <reason>'")
    parser.add_argument("--next", required=True, help="next skill name or 'done'")
    parser.add_argument("--artifact", required=True, help="path to prior artifact (may be empty)")
    parser.add_argument("--orientation", required=True, help="one-line orientation")
    parser.add_argument(
        "--taste-test",
        default=None,
        help="optional taste_test: keyed preamble line (omitted when absent)",
    )
    parser.add_argument(
        "--durable-flags",
        default=None,
        help="optional durable_flags: keyed preamble line (omitted when absent)",
    )
    parser.add_argument(
        "--baseline",
        default=None,
        help="optional baseline: keyed preamble line (omitted when absent)",
    )
    parser.add_argument("--body-file", default=None, help="optional path to body content")
    parser.add_argument(
        "--phase",
        default=None,
        help=(
            "name of THIS phase's own directory under .cheese/ "
            "(path authority). Optional for backward compatibility; "
            "when omitted, falls back to --next."
        ),
    )
    parser.add_argument(
        "--root",
        default=None,
        help="repo root (default: cwd); .cheese/<phase|next>/<slug>.md is written under this",
    )
    parser.set_defaults(func=_cmd_write)


if __name__ == "__main__":
    if "--json" in sys.argv and "--slug" not in sys.argv:
        _run_json_request()
    cli.run(_setup)
