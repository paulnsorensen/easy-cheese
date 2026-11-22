"""Emit a request-bound planner writer brief from the published contract."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import cast

import fromargs

# The producer owns the contract loader that normalize-planner uses, so the
# brief reads the request the same way instead of keeping a second loader.
from easy_cheese.skills.mold.producer import FinalizationError, _load_contract  # pyright: ignore[reportPrivateUsage]
from easy_cheese_schemas.contracts import AgentWriterView, PlannerRequest
from easy_cheese_schemas.schema_runtime import schema_bytes

_REF = re.compile(r'"\$ref": "#/\$defs/([^"]+)"')


def _obj(node: object) -> dict[str, object]:
    return cast(dict[str, object], node)


def _planner_schema() -> dict[str, object]:
    """Narrow the writer schema to the planner_result branch and the defs it reaches."""
    schema = _obj(cast(object, json.loads(schema_bytes(AgentWriterView))))
    defs = _obj(schema["$defs"])
    root = _obj(defs["AgentWriterView"])
    branches = cast(list[dict[str, object]], _obj(cast(list[object], root["allOf"])[0])["oneOf"])
    branch = next(b for b in branches if _obj(_obj(b["properties"])["kind"])["const"] == "planner_result")
    root["allOf"] = [branch]
    root["properties"] = {"kind": {"const": "planner_result", "type": "string"}, "payload": _obj(branch["properties"])["payload"]}
    keep = {"AgentWriterView"}
    todo = ["AgentWriterView"]
    while todo:
        for name in set(cast(list[str], _REF.findall(json.dumps(defs[todo.pop()])))) - keep:
            keep.add(name)
            todo.append(name)
    schema["$defs"] = {name: node for name, node in defs.items() if name in keep}
    return schema


def planner_brief(request: str) -> dict[str, object]:
    """Return contract schema, semantic rules, and valid writer examples."""
    try:
        objective = _load_contract(Path(request), PlannerRequest).objective
    except (FinalizationError, OSError, ValueError) as exc:
        raise fromargs.CliError(str(exc), exit_code=2) from exc

    plan = {
        "objective": objective,
        "curds": [
            {
                "key": "work",
                "outcome": "Complete the requested work",
                "scope": {"paths": ["src/example.py"]},
                "outputs": ["The requested behavior"],
                "criteria": [
                    {
                        "description": "The requested behavior is observable",
                        "check": "Run the acceptance check",
                    }
                ],
            }
        ],
    }
    return {
        "objective": objective,
        "schema": _planner_schema(),
        "rules": {
            "envelope": "Return one AgentWriterView JSON object with kind=planner_result and payload=PlannerResultWriterView. Do not return a bare payload.",
            "objective": "Copy the request objective exactly into payload.plan.objective. Do not paraphrase or repair a returned objective.",
            "disposition": "Complete has a plan and no reason or unresolved_work. Partial has a plan and omitted_work uncertainty only, with no reason. Blocked has no plan, and names unresolved_work and reason.",
            "ownership": "Normalize scope paths. Each path has one owner, even when curds run serially or depend on each other. Use non-overlapping scopes or explicit exclusions.",
            "coverage": "Keep all required work. Do not merge curds or discard uncertainty to satisfy validation. Put planning rationale outside fields that forbid it.",
            "example": "Examples use curd key work and path src/example.py only as a shape. Replace them with the actual complete scope and ensure invocation.curd_ids maps every returned key. For blocked output, pass null plan_id and empty curd_ids to normalize-planner.",
        },
        "examples": {
            "complete": {"kind": "planner_result", "payload": {"disposition": "complete", "plan": plan}},
            "partial": {
                "kind": "planner_result",
                "payload": {
                    "disposition": "partial",
                    "plan": plan,
                    "unresolved_work": [{"description": "Name required work omitted from this plan", "scope": "omitted_work"}],
                },
            },
            "blocked": {
                "kind": "planner_result",
                "payload": {
                    "disposition": "blocked",
                    "unresolved_work": [{"description": "Name the work blocked before planning", "scope": "omitted_work"}],
                    "reason": "Name the blocking condition",
                },
            },
        },
    }


def main(argv: list[str] | None = None) -> int:
    return fromargs.App(
        "planner-brief",
        help="Emit the planner writer contract and request-bound examples.",
        help_formatter="plain",
        default_command=planner_brief,
    ).run(argv)
