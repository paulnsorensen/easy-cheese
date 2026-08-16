"""Machine-readable JSON contract for agent-authored Wheypoint deltas."""

from __future__ import annotations

from enum import Enum
from typing import Any

from easy_cheese_schemas import EntryKind, NextMove, TransitionAction
from easy_cheese_schemas import wheypoint as schema


def _ref(name: str) -> dict[str, str]:
    return {"$ref": f"#/$defs/{name}"}


def _nullable(value: dict[str, Any]) -> dict[str, Any]:
    return {"anyOf": [value, {"type": "null"}]}


def _array(item: dict[str, Any]) -> dict[str, Any]:
    return {"type": "array", "items": item, "maxItems": schema._MAX_ITEMS}


def _enum(enum: type[Enum]) -> dict[str, Any]:
    return {"type": "string", "enum": [member.value for member in enum]}


def _object(
    properties: dict[str, Any],
    *,
    required: tuple[str, ...] = (),
    all_of: tuple[dict[str, Any], ...] = (),
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "type": "object",
        "additionalProperties": False,
        "properties": properties,
    }
    if required:
        result["required"] = list(required)
    if all_of:
        result["allOf"] = list(all_of)
    return result


def wheypoint_delta_json_schema() -> dict[str, Any]:
    """Return the complete JSON input contract accepted by ``commit``."""
    bounded_text = {
        "type": "string",
        "minLength": 1,
        "maxLength": schema._MAX_TEXT,
        "pattern": r"\S",
        "description": "Must contain at least one non-whitespace character.",
    }
    session_properties = {
        "harness": _nullable(_ref("BoundedText")),
        "session_id": _nullable(_ref("Identifier")),
        "captured_at": _nullable(_ref("BoundedText")),
    }
    optional_list = {
        "description": "Omitted or null carries the current value forward; [] replaces it with no items.",
    }
    definitions = {
        "Identifier": {
            "type": "string",
            "pattern": f"^(?:{schema._ID_RE.pattern})$",
            "maxLength": schema._MAX_ID,
        },
        "BoundedText": bounded_text,
        "Digest": {
            "type": "string",
            "pattern": f"^(?:{schema._DIGEST_RE.pattern})$",
        },
        "NextMove": _enum(NextMove),
        "EntryKind": _enum(EntryKind),
        "TransitionAction": _enum(TransitionAction),
        "NextAction": _object(
            {
                "move": _ref("NextMove"),
                "orientation": _ref("BoundedText"),
                "artifact": _nullable(_ref("BoundedText")),
            },
            required=("move", "orientation"),
        ),
        "ProposedEntry": _object(
            {
                "kind": _ref("EntryKind"),
                "summary": _ref("BoundedText"),
                "blocks_continuation": {"type": "boolean", "default": False},
            },
            required=("kind", "summary"),
            all_of=(
                {
                    "if": {
                        "properties": {"kind": {"const": EntryKind.DECISION.value}},
                        "required": ["kind"],
                    },
                    "then": {"properties": {"blocks_continuation": {"const": False}}},
                },
            ),
        ),
        **{
            f"{kind.value.title()}Entry": {
                "allOf": [
                    _ref("ProposedEntry"),
                    {"properties": {"kind": {"const": kind.value}}},
                ]
            }
            for kind in EntryKind
        },
        "ArtifactLink": _object(
            {
                "path": _ref("BoundedText"),
                "digest": _nullable(_ref("Digest")),
                "revision_id": _nullable(_ref("Identifier")),
                "covers_entry_ids": {
                    **_array(_ref("Identifier")),
                    "default": [],
                },
            },
            required=("path",),
        ),
        "EntryTransition": _object(
            {
                "entry_id": _ref("Identifier"),
                "action": _ref("TransitionAction"),
                "rationale": _ref("BoundedText"),
                "target_entry_id": _nullable(_ref("Identifier")),
            },
            required=("entry_id", "action", "rationale"),
            all_of=(
                {
                    "if": {
                        "properties": {
                            "action": {"const": TransitionAction.SUPERSEDE.value}
                        },
                        "required": ["action"],
                    },
                    "then": {
                        "required": ["target_entry_id"],
                        "properties": {"target_entry_id": _ref("Identifier")},
                    },
                    "else": {"properties": {"target_entry_id": {"type": "null"}}},
                },
            ),
        ),
        "DossierOption": _object(
            {
                "option": _ref("BoundedText"),
                "evidence": _array(_ref("BoundedText")),
                "breaks": _ref("BoundedText"),
            },
            required=("option", "evidence", "breaks"),
        ),
        "DecisionFork": _object(
            {
                "fork": _ref("BoundedText"),
                "options": {
                    **_array(_ref("DossierOption")),
                    "minItems": 1,
                },
                "prior_leaning": _nullable(_ref("BoundedText")),
            },
            required=("fork", "options"),
        ),
        "SessionProvenance": _object(session_properties),
        "GenesisSessionProvenance": _object(
            {
                **session_properties,
                "captured_at": _ref("BoundedText"),
            },
            required=("captured_at",),
        ),
    }
    properties = {
        "work_id": _ref("Identifier"),
        "expected_revision_id": _ref("Identifier"),
        "orientation": _nullable(_ref("BoundedText")),
        "working_context": {
            **_nullable(_array(_ref("BoundedText"))),
            **optional_list,
        },
        "next_action": _nullable(_ref("NextAction")),
        "decision_dossier": {
            **_nullable(_array(_ref("DecisionFork"))),
            **optional_list,
        },
        "add_decisions": {
            **_nullable(_array(_ref("DecisionEntry"))),
            **optional_list,
        },
        "add_questions": {
            **_nullable(_array(_ref("QuestionEntry"))),
            **optional_list,
        },
        "add_blockers": {
            **_nullable(_array(_ref("BlockerEntry"))),
            **optional_list,
        },
        "add_artifact_links": {
            **_nullable(_array(_ref("ArtifactLink"))),
            **optional_list,
        },
        "transitions": {
            **_nullable(_array(_ref("EntryTransition"))),
            **optional_list,
        },
        "compacted": {"type": "boolean", "default": False},
        "rehydrated_from_revision_id": _nullable(_ref("Identifier")),
        "session_provenance": _nullable(_ref("SessionProvenance")),
    }
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "WheypointDelta",
        "type": "object",
        "additionalProperties": False,
        "required": ["work_id", "expected_revision_id"],
        "properties": properties,
        "$defs": definitions,
        "allOf": [
            {
                "if": {
                    "properties": {"expected_revision_id": {"const": "genesis"}},
                    "required": ["expected_revision_id"],
                },
                "then": {
                    "required": [
                        "orientation",
                        "working_context",
                        "next_action",
                        "session_provenance",
                    ],
                    "properties": {
                        "orientation": _ref("BoundedText"),
                        "working_context": _array(_ref("BoundedText")),
                        "next_action": _ref("NextAction"),
                        "session_provenance": _ref("GenesisSessionProvenance"),
                        "compacted": {"const": False},
                        "transitions": {
                            "anyOf": [
                                {"type": "null"},
                                {"type": "array", "maxItems": 0},
                            ]
                        },
                    },
                },
            },
            {
                "if": {
                    "properties": {"rehydrated_from_revision_id": {"type": "string"}},
                    "required": ["rehydrated_from_revision_id"],
                },
                "then": {"properties": {"compacted": {"const": True}}},
            },
        ],
        "x-wheypoint-contract": {
            "genesis": {
                "sentinel": "genesis",
                "required": [
                    "orientation",
                    "working_context",
                    "next_action",
                    "session_provenance.captured_at",
                ],
                "forbidden": ["compacted: true", "non-empty transitions"],
            },
            "omitted_or_null": "carry forward unchanged",
            "empty_list": "replace with no items",
            "invariants": [
                "add_decisions, add_questions, and add_blockers accept only their matching entry kind",
                "decision entries cannot block continuation",
                "a record with a gating question or blocker requires a non-empty decision_dossier",
                "each transition names one active existing entry at most once; supersede also names its successor",
            ],
            "limits": {
                "text_characters": schema._MAX_TEXT,
                "list_items": schema._MAX_ITEMS,
            },
        },
    }
