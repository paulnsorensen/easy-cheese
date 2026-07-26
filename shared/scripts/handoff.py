"""Versioned WorkRecord handoffs plus bounded legacy-preamble migration.

`HandoffEnvelope`, `render_handoff`, `load_handoff`, and `resolve_next` define
the authoritative block-YAML phase contract used by `handoff-commit` and
`handoff-resolve`. The line-oriented `HandoffSlug` parser remains only so
`work migrate` can import recognized historical notes without modifying their
sources; new workflow documentation and emitters must not route through it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# Flag propagation rules — see skills/cheese/references/handoff-gate.md § Flag propagation.
ALWAYS_PROPAGATE: frozenset[str] = frozenset({"--hard"})
CHAIN_ONLY: frozenset[str] = frozenset({"--auto"})


@dataclass(frozen=True)
class HandoffSlug:
    status: str  # "ok" or "halt"
    halt_reason: str | None
    next_skill: str  # bare skill name (no leading slash) or "done"
    artifact: str | None
    orientation: str
    taste_test: str | None = None
    durable_flags: str | None = None
    baseline: str | None = None

    def is_halt(self) -> bool:
        return self.status == "halt"


_STATUS_RE = re.compile(r"^status:\s*(?P<rest>.+?)\s*$")
_NEXT_RE = re.compile(r"^next:\s*(?P<value>\S.*?)\s*$")
_ARTIFACT_RE = re.compile(r"^artifact:\s*(?P<value>.*?)\s*$")
# Optional keyed lines allowed between `artifact:` and the orientation.
_OPTIONAL_KEY_RE = re.compile(r"^(?P<key>taste_test|durable_flags|baseline):\s*(?P<value>.*?)\s*$")


class HandoffParseError(ValueError):
    """Raised when a handoff preamble cannot be parsed."""


def _parse_status(line: str) -> tuple[str, str | None]:
    match = _STATUS_RE.match(line)
    if not match:
        raise HandoffParseError(f"expected 'status:' line, got {line!r}")
    rest = match.group("rest")
    if rest == "ok":
        return "ok", None
    if rest.startswith("halt:"):
        reason = rest[len("halt:") :].strip()
        if not reason:
            raise HandoffParseError("halt status requires a reason after 'halt:'")
        return "halt", reason
    raise HandoffParseError(f"status must be 'ok' or 'halt: <reason>', got {rest!r}")


def parse_handoff_slug(text: str) -> HandoffSlug:
    """Parse the preamble from the top of an artifact body.

    The preamble is strictly the first *physical* lines: status, next,
    artifact (value may be empty), zero or more optional keyed lines
    (`taste_test:`, `durable_flags:`, `baseline:`), orientation. Treating blank lines as
    skippable would let a missing orientation silently consume the first
    body line (e.g. a `# Press Report` heading) as the orientation.
    """
    raw_lines = text.splitlines()
    if len(raw_lines) < 4:
        raise HandoffParseError(
            f"handoff preamble needs status / next / artifact / orientation; got {len(raw_lines)} lines"
        )
    status, halt_reason = _parse_status(raw_lines[0])

    next_match = _NEXT_RE.match(raw_lines[1])
    if not next_match:
        raise HandoffParseError(f"expected 'next:' line, got {raw_lines[1]!r}")
    next_skill = next_match.group("value").lstrip("/")

    artifact_match = _ARTIFACT_RE.match(raw_lines[2])
    if not artifact_match:
        raise HandoffParseError(f"expected 'artifact:' line, got {raw_lines[2]!r}")
    artifact_value = artifact_match.group("value") or None

    optional: dict[str, str] = {}
    index = 3
    while index < len(raw_lines):
        keyed_match = _OPTIONAL_KEY_RE.match(raw_lines[index])
        if not keyed_match:
            break
        key = keyed_match.group("key")
        value = keyed_match.group("value")
        if key in optional:
            raise HandoffParseError(f"duplicate '{key}:' line in handoff preamble")
        if not value:
            raise HandoffParseError(f"'{key}:' line requires a value")
        optional[key] = value
        index += 1

    if index >= len(raw_lines):
        raise HandoffParseError("orientation line missing after keyed preamble lines")
    orientation = raw_lines[index].strip()
    if not orientation:
        raise HandoffParseError("orientation line must be non-empty")

    return HandoffSlug(
        status=status,
        halt_reason=halt_reason,
        next_skill=next_skill,
        artifact=artifact_value,
        orientation=orientation,
        taste_test=optional.get("taste_test"),
        durable_flags=optional.get("durable_flags"),
        baseline=optional.get("baseline"),
    )


def render_handoff_slug(slug: HandoffSlug) -> str:
    """Render a HandoffSlug back to its canonical preamble."""
    if slug.status == "halt":
        if not slug.halt_reason:
            raise ValueError("halt status requires halt_reason")
        status_line = f"status: halt: {slug.halt_reason}"
    elif slug.status == "ok":
        status_line = "status: ok"
    else:
        raise ValueError(f"unknown status {slug.status!r}")
    lines = [status_line, f"next: {slug.next_skill}", f"artifact: {slug.artifact or ''}"]
    if slug.taste_test is not None:
        lines.append(f"taste_test: {slug.taste_test}")
    if slug.durable_flags is not None:
        lines.append(f"durable_flags: {slug.durable_flags}")
    if slug.baseline is not None:
        lines.append(f"baseline: {slug.baseline}")
    lines.append(slug.orientation)
    return "\n".join(lines)


# ----- skill dispatch + flag propagation -----------------------------------

_DISPATCH_RE = re.compile(r"^/(?P<skill>[a-z][a-z-]*)\b\s*(?P<args>.*)$")


def parse_skill_dispatch(dispatch: str) -> tuple[str, list[str]]:
    """Split '/age <slug> --hard' into ('age', ['<slug>', '--hard'])."""
    match = _DISPATCH_RE.match(dispatch.strip())
    if not match:
        raise ValueError(f"not a skill dispatch: {dispatch!r}")
    args = match.group("args").split()
    return match.group("skill"), args


def propagate_flags(source_flags: list[str], *, in_auto_chain: bool) -> list[str]:
    """Return the subset of source flags that survive the propagation rules."""
    result: list[str] = []
    for flag in source_flags:
        bare = flag.split("=", 1)[0]
        if bare in ALWAYS_PROPAGATE or bare in CHAIN_ONLY and in_auto_chain:
            result.append(flag)
    return result


# Versioned contract runtime --------------------------------------------------

CONTRACT_VERSION = "cheese-handoff/v1"
RESERVED_NEXT = frozenset({"done", "hold", "tasks"})
_ENVELOPE_KEYS = frozenset({"contract_version", "work_id", "attempt_id", "operation_id", "phase", "status", "halt_reason", "next", "artifact", "payload", "provenance"})
_SCHEMA_TYPES = frozenset({"string", "integer", "boolean", "mapping", "list"})


@dataclass(frozen=True)
class HandoffEnvelope:
    contract_version: str
    work_id: str
    attempt_id: str
    operation_id: str
    phase: str
    status: str
    halt_reason: str | None
    next: str
    artifact: str
    payload: dict
    provenance: dict

    @classmethod
    def from_mapping(cls, value: dict) -> "HandoffEnvelope":
        if not isinstance(value, dict):
            raise HandoffParseError("handoff frontmatter must be a mapping")
        required = _ENVELOPE_KEYS - {"halt_reason", "payload", "provenance"}
        missing = required - value.keys()
        extra = value.keys() - _ENVELOPE_KEYS
        if missing:
            raise HandoffParseError(f"handoff envelope missing: {', '.join(sorted(missing))}")
        if extra:
            raise HandoffParseError(f"handoff envelope has unknown keys: {', '.join(sorted(extra))}")
        return cls(**{key: value.get(key, {} if key in {"payload", "provenance"} else None) for key in _ENVELOPE_KEYS})

    def as_mapping(self) -> dict:
        return {
            "contract_version": self.contract_version,
            "work_id": self.work_id,
            "attempt_id": self.attempt_id,
            "operation_id": self.operation_id,
            "phase": self.phase,
            "status": self.status,
            "halt_reason": self.halt_reason,
            "next": self.next,
            "artifact": self.artifact,
            "payload": self.payload,
            "provenance": self.provenance,
        }


def _yaml():
    try:
        import yaml
    except ImportError as exc:
        raise HandoffParseError("PyYAML is required; install easy-cheese's Cheese companion runtime") from exc
    return yaml


def parse_handoff(text: str, loaded_path: str | Path) -> HandoffEnvelope:
    """Parse an artifact's YAML envelope and bind it to the loaded path."""
    if not text.startswith("---\n"):
        raise HandoffParseError("handoff requires YAML frontmatter")
    end = text.find("\n---\n", 4)
    if end < 0:
        raise HandoffParseError("handoff frontmatter is not closed")
    try:
        raw = _yaml().safe_load(text[4:end])
    except Exception as exc:
        raise HandoffParseError(f"invalid handoff YAML: {exc}") from exc
    envelope = HandoffEnvelope.from_mapping(raw)
    actual = Path(loaded_path).expanduser().resolve()
    declared = Path(envelope.artifact).expanduser()
    if not declared.is_absolute():
        declared = (Path.cwd() / declared).resolve()
    if actual != declared:
        raise HandoffParseError(f"artifact path mismatch: {envelope.artifact!r} != {str(actual)!r}")
    return envelope


def render_handoff(envelope: HandoffEnvelope, body: str = "", contracts: dict | None = None) -> str:
    errors = validate_handoff(envelope, contracts)
    if errors:
        raise ValueError("; ".join(errors))
    frontmatter = _yaml().safe_dump(envelope.as_mapping(), sort_keys=False, allow_unicode=True).rstrip()
    return f"---\n{frontmatter}\n---\n" + (f"\n{body}" if body else "")


def _schema_error(schema: object, path: str = "payload") -> str | None:
    if not isinstance(schema, dict):
        return f"{path} schema must be a mapping"
    allowed = {"type", "required", "nullable", "fields", "items"}
    unknown = set(schema) - allowed
    if unknown:
        return f"{path} schema has unsupported keys: {', '.join(sorted(unknown))}"
    kind = schema.get("type")
    if kind not in _SCHEMA_TYPES:
        return f"{path} schema has unsupported type {kind!r}"
    if any(not isinstance(schema.get(key), bool) for key in ("required", "nullable") if key in schema):
        return f"{path} schema required and nullable must be booleans"
    if kind == "mapping":
        fields = schema.get("fields", {})
        if not isinstance(fields, dict):
            return f"{path}.fields must be a mapping"
        for name, child in fields.items():
            if not isinstance(name, str) or not name:
                return f"{path}.fields keys must be non-empty strings"
            error = _schema_error(child, f"{path}.{name}")
            if error:
                return error
    elif "fields" in schema:
        return f"{path}.fields is only valid for mapping"
    if kind == "list":
        if "items" not in schema:
            return f"{path}.items is required for list"
        return _schema_error(schema["items"], f"{path}[]")
    if "items" in schema:
        return f"{path}.items is only valid for list"
    return None


def _validate_value(value: object, schema: dict, path: str) -> list[str]:
    if value is None:
        return [] if schema.get("nullable", False) else [f"{path} must not be null"]
    kind = schema["type"]
    if kind == "string":
        return [] if isinstance(value, str) else [f"{path} must be a string"]
    if kind == "integer":
        return [] if isinstance(value, int) and not isinstance(value, bool) else [f"{path} must be an integer"]
    if kind == "boolean":
        return [] if isinstance(value, bool) else [f"{path} must be a boolean"]
    if kind == "list":
        if not isinstance(value, list):
            return [f"{path} must be a list"]
        return [error for index, item in enumerate(value) for error in _validate_value(item, schema["items"], f"{path}[{index}]")]
    if not isinstance(value, dict):
        return [f"{path} must be a mapping"]
    fields = schema.get("fields", {})
    errors = [f"{path} has unknown field {key!r}" for key in value.keys() - fields.keys()]
    for name, child in fields.items():
        if name not in value:
            if child.get("required", False):
                errors.append(f"{path}.{name} is required")
        else:
            errors.extend(_validate_value(value[name], child, f"{path}.{name}"))
    return errors


def _payload_schema(raw: object, path: Path) -> dict:
    if not isinstance(raw, dict):
        raise ValueError(f"malformed payload schema: {path}")
    schema = raw if "type" in raw else {"type": "mapping", "fields": raw}
    error = _schema_error(schema)
    if error:
        raise ValueError(f"malformed payload schema in {path}: {error}")
    return schema


def validate_handoff(envelope: HandoffEnvelope, contracts: dict | None = None) -> list[str]:
    errors: list[str] = []
    if envelope.contract_version != CONTRACT_VERSION:
        errors.append(f"unsupported contract_version {envelope.contract_version!r}")
    if envelope.status not in {"ok", "halt"}:
        errors.append("status must be 'ok' or 'halt'")
    if envelope.status == "halt" and (not isinstance(envelope.halt_reason, str) or not envelope.halt_reason.strip()):
        errors.append("halt requires a non-empty halt_reason")
    if envelope.status == "ok" and envelope.halt_reason is not None:
        errors.append("ok forbids halt_reason")
    for name in ("work_id", "attempt_id", "operation_id", "phase", "next", "artifact"):
        if not isinstance(getattr(envelope, name), str) or not getattr(envelope, name).strip():
            errors.append(f"{name} must be a non-empty string")
    if not isinstance(envelope.payload, dict):
        errors.append("payload must be a mapping")
    if not isinstance(envelope.provenance, dict):
        errors.append("provenance must be a mapping")
    phases = (contracts or {}).get("phases", contracts or {})
    if phases:
        source = phases.get(envelope.phase)
        if source is None:
            errors.append(f"unknown source phase {envelope.phase!r}")
        elif envelope.next not in source["next"]:
            errors.append(f"disallowed transition: {envelope.phase} -> {envelope.next}")
        if envelope.next not in RESERVED_NEXT and envelope.next not in phases:
            errors.append(f"unknown next phase {envelope.next!r}")
        if source is not None and isinstance(envelope.payload, dict) and envelope.next != "tasks":
            errors.extend(_validate_value(envelope.payload, source["payload"], "payload"))
    if envelope.next == "tasks":
        tasks = envelope.payload.get("tasks") if isinstance(envelope.payload, dict) else None
        if not isinstance(tasks, list) or not tasks:
            errors.append("tasks requires a non-empty payload.tasks list")
        else:
            for index, task in enumerate(tasks):
                if not isinstance(task, dict) or set(task) - {"phase", "subject", "input"}:
                    errors.append(f"payload.tasks[{index}] must be a phase directive")
                    continue
                if not isinstance(task.get("phase"), str) or task["phase"] not in phases:
                    errors.append(f"payload.tasks[{index}].phase must name a registered phase")
                if not isinstance(task.get("subject"), str) or not task["subject"].strip():
                    errors.append(f"payload.tasks[{index}].subject must be a non-empty string")
                if "input" in task and not isinstance(task["input"], dict):
                    errors.append(f"payload.tasks[{index}].input must be a mapping")
    return errors


def resolve_next(
    envelope: HandoffEnvelope,
    available_phases: list[str] | set[str] | tuple[str, ...],
    contracts: dict,
) -> dict[str, Any]:
    """Resolve a validated destination without rewriting persisted lifecycle state."""
    errors = validate_handoff(envelope, contracts)
    if errors:
        raise ValueError("; ".join(errors))
    if not isinstance(available_phases, (list, set, tuple)) or not all(
        isinstance(phase, str) and phase for phase in available_phases
    ):
        raise ValueError("available_phases must contain phase names")
    if envelope.status == "halt":
        return {
            "action": "halt",
            "reason": envelope.halt_reason,
            "next": envelope.next,
        }
    if envelope.next == "done":
        return {"action": "done"}
    if envelope.next == "hold":
        return {"action": "hold"}
    if envelope.next == "tasks":
        return {"action": "tasks", "tasks": envelope.payload["tasks"]}
    if envelope.next in set(available_phases):
        return {"action": "dispatch", "phase": envelope.next}
    return {"action": "unavailable", "phase": envelope.next}


def assemble_transition_registry(contract_paths) -> dict:
    """Compile and validate phase-owned contracts into the global registry."""
    registry = {"phases": {}}
    for raw_path in contract_paths:
        path = Path(raw_path)
        try:
            data = _yaml().safe_load(path.read_text(encoding="utf-8"))
        except Exception as exc:
            raise ValueError(f"malformed phase contract: {path}") from exc
        if not isinstance(data, dict) or set(data) != {"phase", "next", "payload"}:
            raise ValueError(f"malformed phase contract: {path}")
        phase, outgoing = data["phase"], data["next"]
        if not isinstance(phase, str) or not re.fullmatch(r"[a-z][a-z-]*", phase):
            raise ValueError(f"malformed phase declaration: {path}")
        if phase in RESERVED_NEXT or phase in registry["phases"]:
            raise ValueError(f"duplicate or reserved phase declaration: {phase}")
        if not isinstance(outgoing, list) or len(outgoing) != len(set(outgoing)) or not all(isinstance(item, str) for item in outgoing):
            raise ValueError(f"malformed outgoing transitions: {path}")
        registry["phases"][phase] = {"next": outgoing, "payload": _payload_schema(data["payload"], path)}
    for phase, contract in registry["phases"].items():
        invalid = set(contract["next"]) - set(registry["phases"]) - RESERVED_NEXT
        if invalid:
            raise ValueError(f"{phase} names unknown destinations: {', '.join(sorted(invalid))}")
    return registry
