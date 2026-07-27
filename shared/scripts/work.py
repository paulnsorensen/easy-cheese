"""Durable, revision-checked workflow continuity records."""
from __future__ import annotations

from contextlib import contextmanager
import json
import re
import tempfile
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable

import handoff
import yaml

try:
    from paths import local_work_snapshot_path, project_key, work_record_path, worktree_key
except ImportError:  # package-style import for external consumers
    from shared.scripts.paths import (
        local_work_snapshot_path,
        project_key,
        work_record_path,
        worktree_key,
    )

NONTERMINAL = {"active", "paused", "blocked"}
TERMINAL = {"completed", "abandoned"}


@dataclass
class WorkAttempt:
    attempt_id: str
    worktree_key: str
    status: str = "active"
    current_phase: str | None = None
    artifacts: list[dict[str, Any]] = field(default_factory=list)
    context: str = ""


@dataclass
class WorkRecord:
    work_id: str
    slug: str
    title: str
    project_key: str
    status: str = "active"
    revision: int = 0
    attempts: list[WorkAttempt] = field(default_factory=list)
    working_context: str = ""
    decisions: str = ""
    parked: str = ""
    open_questions: str = ""
    context_log: list[str] = field(default_factory=list)
    tasks: list[dict[str, Any]] = field(default_factory=list)
    abandonment_reason: str | None = None

    def to_mapping(self) -> dict[str, Any]:
        return {"schema_version": "cheese-work/v1", **asdict(self)}


def _slug(subject: str) -> str:
    words = re.findall(r"[a-z0-9]+", subject.lower())
    return "-".join(words)[:64] or "work"


def _validate_identifier(value: str, label: str, prefix: str) -> str:
    if (
        not isinstance(value, str)
        or not value.startswith(prefix)
        or Path(value).name != value
        or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{1,127}", value)
    ):
        raise ValueError(f"invalid {label}")
    return value


def _record_from_mapping(mapping: object) -> WorkRecord:
    if not isinstance(mapping, dict):
        raise ValueError("work record frontmatter must be a mapping")
    data = dict(mapping)
    if data.pop("schema_version", None) != "cheese-work/v1":
        raise ValueError("unsupported work record")
    attempts = data.get("attempts", [])
    if not isinstance(attempts, list) or not all(isinstance(item, dict) for item in attempts):
        raise ValueError("invalid work record attempts")
    data["attempts"] = [WorkAttempt(**item) for item in attempts]
    return WorkRecord(**data)


def _render(record: WorkRecord) -> str:
    body = (
        f"# {record.title}\n\n## Working context\n{record.working_context}\n\n"
        f"## Decisions\n{record.decisions}\n\n## Parked\n{record.parked}\n\n"
        f"## Open questions\n{record.open_questions}\n\n## Attempts\n"
        + "".join(f"### {a.attempt_id}\n{a.context}\n\n" for a in record.attempts)
        + "## Context log\n"
        + "\n".join(record.context_log)
        + "\n"
    )
    frontmatter = yaml.safe_dump(
        record.to_mapping(), sort_keys=False, allow_unicode=True
    ).rstrip("\n")
    return f"---\n{frontmatter}\n---\n{body}"


def _decode(path: Path) -> WorkRecord:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        raise ValueError(f"invalid work record: {path}")
    end = text.find("\n---\n", 4)
    if end < 0:
        raise ValueError(f"invalid work record: {path}")
    try:
        return _record_from_mapping(yaml.safe_load(text[4:end]))
    except (yaml.YAMLError, TypeError, ValueError, handoff.HandoffParseError) as exc:
        raise ValueError(f"invalid work record: {path}") from exc


def _atomic_write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
        handle.write(text)
        temporary = Path(handle.name)
    temporary.replace(path)
    return path


def _save(record: WorkRecord, path: Path | None = None) -> Path:
    return _atomic_write(path or work_record_path(record.work_id, record.project_key), _render(record))


def _journal_path(record: WorkRecord, operation_id: str) -> Path:
    operation = _validate_identifier(operation_id, "operation_id", "op_")
    return work_record_path(record.work_id, record.project_key).parent / "operations" / f"{operation}.json"


def _write_journal(path: Path, entry: dict[str, Any]) -> None:
    _atomic_write(path, json.dumps(entry, sort_keys=True, indent=2) + "\n")


@contextmanager
def record_lock(record: WorkRecord):
    """Serialize all journal and record updates for one WorkRecord."""
    lock_path = work_record_path(record.work_id, record.project_key).parent / ".lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+", encoding="utf-8") as handle:
        try:
            import fcntl
        except ImportError as exc:
            raise OSError("work record updates require a POSIX file lock") from exc
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _finish_record_mutation(entry: dict[str, Any], record: WorkRecord) -> WorkRecord:
    candidate = _record_from_mapping(entry.get("result"))
    if record.to_mapping() != candidate.to_mapping():
        if record.revision != entry.get("expected_revision"):
            raise ValueError("prepared work mutation conflicts with durable record")
        _save(candidate)
    entry["complete"] = True
    _write_journal(Path(entry["journal"]), entry)
    return candidate


def _recover_record_mutations(record: WorkRecord) -> WorkRecord:
    journal_root = _journal_path(record, "op_placeholder").parent
    for path in sorted(journal_root.glob("*.json")):
        entry = json.loads(path.read_text(encoding="utf-8"))
        if entry.get("kind") == "work-mutation" and not entry.get("complete"):
            record = _finish_record_mutation(entry, record)
    return record


def load_work(
    work_id: str,
    project: str | None = None,
    *,
    include_local: bool = True,
    repo_root: Path | str | None = None,
) -> WorkRecord:
    durable = work_record_path(work_id, project)
    local = local_work_snapshot_path(work_id, repo_root)
    if durable.is_file():
        record = _decode(durable)
        if include_local and local.is_file() and _decode(local).to_mapping() != record.to_mapping():
            raise ValueError("divergent durable and local work snapshots require reconciliation")
        return record
    if include_local and local.is_file():
        record = _decode(local)
        _save(record)
        return record
    raise FileNotFoundError(durable)


def _find_attempt(record: WorkRecord, attempt_id: str) -> WorkAttempt:
    try:
        return next(a for a in record.attempts if a.attempt_id == attempt_id)
    except StopIteration as exc:
        raise ValueError(f"unknown attempt {attempt_id!r}") from exc


def _derive_status(record: WorkRecord) -> None:
    if record.abandonment_reason is not None:
        record.status = "abandoned"
        return
    attempts = [a.status for a in record.attempts if a.status in NONTERMINAL]
    tasks = [t["status"] for t in record.tasks if t["status"] not in TERMINAL]
    if any(status == "active" for status in attempts) or any(s in {"pending", "active"} for s in tasks):
        record.status = "active"
    elif attempts or tasks:
        record.status = "blocked" if all(s == "blocked" for s in attempts + tasks) else "paused"
    else:
        record.status = "completed"


def _mutate(
    work_id: str,
    expected_revision: int,
    operation_id: str,
    apply: Callable[[WorkRecord], None],
    project: str | None = None,
) -> WorkRecord:
    operation_id = _validate_identifier(operation_id, "operation_id", "op_")
    record = load_work(work_id, project, include_local=False)
    with record_lock(record):
        record = load_work(work_id, project, include_local=False)
        record = _recover_record_mutations(record)
        journal = _journal_path(record, operation_id)
        if journal.is_file():
            entry = json.loads(journal.read_text(encoding="utf-8"))
            if entry.get("kind") != "work-mutation" or entry.get("expected_revision") != expected_revision:
                raise ValueError("operation does not match prepared journal")
            if entry.get("complete"):
                return _record_from_mapping(entry["result"])
            return _finish_record_mutation(entry, record)
        if record.revision != expected_revision:
            raise ValueError("stale work revision")
        candidate = _record_from_mapping(record.to_mapping())
        apply(candidate)
        _derive_status(candidate)
        candidate.revision += 1
        entry = {
            "kind": "work-mutation",
            "operation_id": operation_id,
            "expected_revision": expected_revision,
            "complete": False,
            "journal": str(journal),
            "result": candidate.to_mapping(),
        }
        _write_journal(journal, entry)
        _save(candidate)
        entry["complete"] = True
        _write_journal(journal, entry)
        return candidate


def ensure_work(
    work_id: str | None = None,
    subject: str | None = None,
    worktree: str | None = None,
    attempt: dict[str, Any] | str | None = None,
    project: str | None = None,
) -> WorkRecord | None:
    if work_id is None and not (subject and subject.strip()):
        return None
    key = _validate_identifier(worktree or worktree_key(), "worktree_key", "wt_")
    supplied_attempt = attempt.get("attempt_id") if isinstance(attempt, dict) else attempt
    if supplied_attempt is not None:
        supplied_attempt = _validate_identifier(supplied_attempt, "attempt_id", "wa_")
    if work_id is None:
        record = WorkRecord(
            work_id="wk_" + uuid.uuid4().hex,
            slug=_slug(subject or ""),
            title=(subject or "").strip(),
            project_key=project or project_key(),
        )
        record.attempts.append(
            WorkAttempt(
                attempt_id=supplied_attempt or "wa_" + uuid.uuid4().hex,
                worktree_key=key,
            )
        )
        _save(record)
        return record
    record = load_work(work_id, project, include_local=False)
    with record_lock(record):
        record = load_work(work_id, project, include_local=False)
        if record.status in TERMINAL:
            return record
        existing = next(
            (a for a in record.attempts if a.worktree_key == key and a.status in NONTERMINAL),
            None,
        )
        if existing is None:
            record.attempts.append(
                WorkAttempt(supplied_attempt or "wa_" + uuid.uuid4().hex, key)
            )
            _derive_status(record)
            record.revision += 1
            _save(record)
        return record


def apply_work_patch(record: WorkRecord, attempt: WorkAttempt, patch: dict[str, Any] | None) -> None:
    """Validate and apply the closed WorkPatch shape."""
    if not isinstance(patch, dict) or set(patch) - {"scope", "attempt_id", "changes"}:
        raise ValueError("invalid work patch")
    scope = patch.get("scope")
    changes = patch.get("changes", [])
    if scope not in {"work", "attempt"} or not isinstance(changes, list):
        raise ValueError("invalid work patch")
    if scope == "work" and "attempt_id" in patch:
        raise ValueError("work patch forbids attempt_id")
    if scope == "attempt" and patch.get("attempt_id") != attempt.attempt_id:
        raise ValueError("attempt patch mismatch")
    target = record if scope == "work" else attempt
    allowed = {"working_context", "decisions", "parked", "open_questions"} if scope == "work" else {"attempt_context"}
    for change in changes:
        if (
            not isinstance(change, dict)
            or set(change) != {"section", "operation", "value"}
            or change["section"] not in allowed
            or change["operation"] not in {"replace", "append"}
            or not isinstance(change["value"], str)
        ):
            raise ValueError("invalid work patch")
        attribute = "context" if change["section"] == "attempt_context" else change["section"]
        value = change["value"] if change["operation"] == "replace" else getattr(target, attribute) + change["value"]
        setattr(target, attribute, value)


def patch_work(
    work_id: str,
    expected_revision: int,
    scope: str,
    patch: dict[str, Any],
    attempt_id: str | None = None,
    operation_id: str | None = None,
    project: str | None = None,
) -> WorkRecord:
    if scope not in {"work", "attempt"} or patch.get("scope") != scope:
        raise ValueError("invalid work patch")
    if scope == "work" and (attempt_id is not None or "attempt_id" in patch):
        raise ValueError("work patch forbids attempt_id")
    if scope == "attempt" and (
        attempt_id is None or patch.get("attempt_id") != attempt_id
    ):
        raise ValueError("attempt patch mismatch")

    def apply(record: WorkRecord) -> None:
        attempt = _find_attempt(record, attempt_id) if attempt_id else record.attempts[0]
        apply_work_patch(record, attempt, patch)

    return _mutate(work_id, expected_revision, operation_id or "", apply, project)


def transition_attempt(
    work_id: str, expected_revision: int, patch: dict[str, Any], operation_id: str, project: str | None = None
) -> WorkRecord:
    if set(patch) - {"attempt_id", "target_status", "reason"}:
        raise ValueError("invalid attempt transition")
    target = patch.get("target_status")
    reason = patch.get("reason")
    if target not in NONTERMINAL | {"abandoned"} or bool(reason) != (target in {"blocked", "abandoned"}):
        raise ValueError("invalid attempt transition")

    def apply(record: WorkRecord) -> None:
        attempt = _find_attempt(record, patch.get("attempt_id", ""))
        if attempt.status in TERMINAL:
            raise ValueError("terminal attempt cannot reopen")
        attempt.status = target

    return _mutate(work_id, expected_revision, operation_id, apply, project)


def claim_task(work_id: str, task_id: str, attempt_id: str, expected_revision: int, operation_id: str, project: str | None = None) -> WorkRecord:
    _validate_identifier(attempt_id, "attempt_id", "wa_")

    def apply(record: WorkRecord) -> None:
        task = next((t for t in record.tasks if t["task_id"] == task_id), None)
        if task is None or task["status"] != "pending":
            raise ValueError("task is not pending")
        attempt = _find_attempt(record, attempt_id)
        if attempt.status not in NONTERMINAL or attempt.current_phase not in {None, task["phase"]}:
            raise ValueError("claiming attempt is not active for task phase")
        attempt.current_phase = task["phase"]
        task.update(status="active", attempt_id=attempt_id)

    return _mutate(work_id, expected_revision, operation_id, apply, project)


def transition_task(work_id: str, task_id: str, target_status: str, expected_revision: int, reason: str | None, operation_id: str, project: str | None = None) -> WorkRecord:
    if target_status not in {"pending", "blocked", "abandoned"} or bool(reason) != (target_status in {"blocked", "abandoned"}):
        raise ValueError("invalid task transition")

    def apply(record: WorkRecord) -> None:
        task = next((t for t in record.tasks if t["task_id"] == task_id), None)
        if task is None or task["status"] in TERMINAL:
            raise ValueError("terminal or unknown task")
        task["status"], task["reason"] = target_status, reason

    return _mutate(work_id, expected_revision, operation_id, apply, project)


def abandon_work(work_id: str, expected_revision: int, reason: str, operation_id: str, project: str | None = None) -> WorkRecord:
    if not reason:
        raise ValueError("abandonment requires reason")

    def apply(record: WorkRecord) -> None:
        record.abandonment_reason = reason
        for attempt in record.attempts:
            if attempt.status in NONTERMINAL:
                attempt.status = "abandoned"
        for task in record.tasks:
            if task["status"] not in TERMINAL:
                task.update(status="abandoned", reason=reason)

    return _mutate(work_id, expected_revision, operation_id, apply, project)


def reopen_work(work_id: str, expected_revision: int, worktree: str, operation_id: str, project: str | None = None) -> WorkRecord:
    key = _validate_identifier(worktree, "worktree_key", "wt_")

    def apply(record: WorkRecord) -> None:
        if record.status not in TERMINAL:
            raise ValueError("only terminal work can reopen")
        record.abandonment_reason = None
        record.attempts.append(WorkAttempt("wa_" + uuid.uuid4().hex, key))

    return _mutate(work_id, expected_revision, operation_id, apply, project)


def list_work(project: str | None = None, worktree: str | None = None, statuses: set[str] | None = None) -> list[WorkRecord]:
    root = work_record_path("placeholder", project).parents[1]
    found: list[WorkRecord] = []
    for path in root.glob("wk_*/index.md"):
        record = _decode(path)
        if statuses and record.status not in statuses:
            continue
        if worktree and not any(a.worktree_key == worktree and a.status in {"active", "paused"} for a in record.attempts):
            continue
        found.append(record)
    return sorted(found, key=lambda r: (r.status, r.title, r.work_id))


def resolve_continue(project: str | None = None, worktree: str | None = None) -> dict[str, Any]:
    key = _validate_identifier(worktree or worktree_key(), "worktree_key", "wt_")
    durable = {record.work_id: record for record in list_work(project, None, {"active", "paused"})}
    local_root = local_work_snapshot_path("wk_placeholder").parents[1]
    for path in local_root.glob("wk_*/index.md"):
        local = _decode(path)
        existing = durable.get(local.work_id)
        if existing is not None and existing.to_mapping() != local.to_mapping():
            raise ValueError("divergent durable and local work snapshots require reconciliation")
        if existing is None:
            _save(local)
            durable[local.work_id] = local
    all_candidates = sorted(durable.values(), key=lambda r: (r.status, r.title, r.work_id))
    scoped = [
        record for record in all_candidates
        if any(a.worktree_key == key and a.status in {"active", "paused"} for a in record.attempts)
    ]
    candidates = scoped or all_candidates
    return {
        "action": "continue" if len(scoped) == 1 else "picker",
        "records": [record.to_mapping() for record in candidates],
    }


def export_work_snapshot(work_id: str, expected_revision: int, repo_root: Path | str | None = None, project: str | None = None) -> Path:
    record = load_work(work_id, project, include_local=False)
    if record.revision != expected_revision:
        raise ValueError("stale work revision")
    return _save(record, local_work_snapshot_path(work_id, repo_root))


_RECONCILERS: dict[str, Callable[[dict[str, Any], WorkRecord], bool]] = {}


def register_reconciler(kind: str, reconciler: Callable[[dict[str, Any], WorkRecord], bool]) -> None:
    """Register a journal recovery callback owned by a higher-level runtime."""
    _RECONCILERS[kind] = reconciler


def reconcile_work(work_id: str, project: str | None = None) -> dict[str, Any]:
    record = load_work(work_id, project, include_local=False)
    reconciled: list[str] = []
    pending: list[str] = []
    with record_lock(record):
        record = load_work(work_id, project, include_local=False)
        journal_root = _journal_path(record, "op_placeholder").parent
        for path in sorted(journal_root.glob("*.json")):
            entry = json.loads(path.read_text(encoding="utf-8"))
            if entry.get("complete"):
                continue
            if entry.get("kind") == "work-mutation":
                try:
                    record = _finish_record_mutation(entry, record)
                except (OSError, ValueError):
                    pending.append(str(path))
                else:
                    reconciled.append(str(path))
                continue
            reconciler = _RECONCILERS.get(entry.get("kind"))
            if reconciler is not None and reconciler(entry, record):
                reconciled.append(str(path))
                record = load_work(work_id, project, include_local=False)
            else:
                pending.append(str(path))
    return {"work_id": work_id, "reconciled": reconciled, "pending": pending}


def _legacy_registry() -> handoff.TransitionRegistry:
    root = Path(__file__).resolve().parents[2]
    return handoff.assemble_transition_registry(root.glob("skills/*/references/handoff-contract.yaml"))


def _migrate_handoff(source: Path, text: str, project: str | None) -> WorkRecord | None:
    lines = text.splitlines()
    if len(lines) < 4 or not lines[1].startswith("next: "):
        return None
    status_line = lines[0]
    if status_line == "status: ok":
        status, halt_reason = "ok", None
    elif status_line.startswith("status: halt: ") and status_line[14:].strip():
        status, halt_reason = "halt", status_line[14:].strip()
    elif status_line.startswith("status: gated: ") and status_line[15:].strip():
        status, halt_reason = "halt", status_line[15:].strip()
    else:
        return None

    original_next = lines[1][len("next: "):].strip()
    tasks = [
        {"phase": item.strip().lstrip("/"), "subject": item.strip().lstrip("/")}
        for item in original_next[1:-1].split(",")
        if item.strip()
    ] if original_next.startswith("[") and original_next.endswith("]") else []
    next_value = "hold" if status_line.startswith("status: gated:") else ("tasks" if tasks else original_next.lstrip("/"))
    registry = _legacy_registry()
    if next_value not in registry.phases["wheypoint"].next:
        return None
    if any(task["phase"] not in registry.phases for task in tasks):
        return None

    title = source.stem.replace("-", " ").strip() or "Imported handoff"
    record = WorkRecord("wk_" + uuid.uuid4().hex, _slug(title), title, project or project_key())
    attempt = WorkAttempt("wa_" + uuid.uuid4().hex, worktree_key(), current_phase="wheypoint")
    record.attempts.append(attempt)
    operation_id = "op_migration_" + uuid.uuid4().hex
    target = Path.cwd() / ".cheese" / "wheypoint" / record.work_id / f"{operation_id}-{record.slug}.md"
    provenance = {
        "legacy": {
            "source_path": str(source.resolve()),
            "status": status_line,
            "next": original_next,
        }
    }
    envelope = handoff.HandoffEnvelope(
        contract_version=handoff.CONTRACT_VERSION,
        work_id=record.work_id,
        attempt_id=attempt.attempt_id,
        operation_id=operation_id,
        phase="wheypoint",
        status=status,
        halt_reason=halt_reason,
        next=next_value,
        artifact=str(target.resolve()),
        payload={"tasks": tasks} if tasks and next_value == "tasks" else {},
        provenance=provenance,
    )
    if handoff.validate_handoff(envelope, registry):
        return None
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(handoff.render_handoff(envelope, text, contracts=registry), encoding="utf-8")
    attempt.artifacts.append({"path": str(target), "phase": "wheypoint", "operation_id": operation_id})
    record.working_context = text
    record.context_log.append(f"migrated:{source.resolve()}")
    if tasks and next_value == "tasks":
        record.tasks = [
            {"task_id": f"{operation_id}:{index}", **task, "status": "pending"}
            for index, task in enumerate(tasks)
        ]
    return record


def migrate_legacy(source_paths: list[Path | str], project: str | None = None) -> dict[str, Any]:
    """Import only recognized legacy records and handoffs without changing sources."""
    migrated: list[str] = []
    skipped: list[str] = []
    for source in map(Path, source_paths):
        try:
            text = source.read_text(encoding="utf-8")
            data = json.loads(text)
        except (OSError, json.JSONDecodeError):
            data = None
        if isinstance(data, dict):
            if set(data) - {"work_id", "title", "slug", "project_key"} or not data.get("work_id") or not data.get("title"):
                skipped.append(str(source))
                continue
            if work_record_path(data["work_id"], project or data.get("project_key")).exists():
                skipped.append(str(source))
                continue
            record = WorkRecord(data["work_id"], data.get("slug") or _slug(data["title"]), data["title"], project or data.get("project_key") or project_key())
        else:
            record = _migrate_handoff(source, text, project)
            if record is None:
                skipped.append(str(source))
                continue
        _save(record)
        migrated.append(str(source))
    return {"migrated": migrated, "skipped": skipped}
