"""Private route checks for handoff and artifact publication."""

from __future__ import annotations

from easy_cheese_schemas import (
    CURD_PLAN_SCHEMA_URI,
    CURD_RESULT_SCHEMA_URI,
    PLANNER_REQUEST_SCHEMA_URI,
)


class RouteError(ValueError):
    pass


_ROUTES: dict[str, dict[str, str]] = {
    "age": {"cure": CURD_PLAN_SCHEMA_URI},
    # Cook runs its Press loop in-phase, so Cook never hands off to Press.
    "cook": {
        "age": CURD_RESULT_SCHEMA_URI,
        "mold": PLANNER_REQUEST_SCHEMA_URI,
    },
    "cure": {"age": CURD_RESULT_SCHEMA_URI},
    "mold": {"cook": CURD_PLAN_SCHEMA_URI},
    # Press hands a finding or a coverage gap back to Cook as a correction.
    "press": {"age": CURD_RESULT_SCHEMA_URI, "cook": CURD_RESULT_SCHEMA_URI},
}


def validate_route(
    source: str, destination: str, payload_schema_uri: str | None = None
) -> None:
    """Reject unknown or mismatched routes before a handoff is written."""
    if source not in _ROUTES:
        raise RouteError(f"unknown source phase {source!r}")
    if destination == "done":
        if payload_schema_uri is not None:
            raise RouteError("terminal transition cannot carry a payload schema")
        return
    expected = _ROUTES[source].get(destination)
    if expected is None:
        raise RouteError(f"transition {source} -> {destination} is not declared")
    if payload_schema_uri is not None and payload_schema_uri != expected:
        raise RouteError(
            f"payload schema {payload_schema_uri!r} is not declared for "
            + f"{source} -> {destination}"
        )
