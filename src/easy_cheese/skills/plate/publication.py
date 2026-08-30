"""Validate terminal Plate publication evidence."""

from __future__ import annotations

import argparse
import copy
import json
import re
import sys
from pathlib import Path
from typing import cast
from urllib.parse import urlparse

_MODES = {"commit-only", "topology-preflight", "new-pr", "existing-pr", "stack-maintenance"}
_TOPOLOGIES = {"single", "stacked", "n/a"}
_PROVIDERS = {"ordinary", "graphite", "git-town", "gh-stack", "n/a"}
_STACK_PROVIDERS = {"graphite", "git-town", "gh-stack"}
_REQUIRED = {"mode", "topology", "provider", "artifacts", "gate", "commits", "prs", "risk"}
_ALLOWED = _REQUIRED | {"pr_plan"}
_SHA = re.compile(r"[0-9a-fA-F]{7,40}")


class PublicationValidationError(ValueError):
    """One or more publication evidence invariants failed."""

    def __init__(self, errors: list[str]) -> None:
        self.errors: tuple[str, ...] = tuple(errors)
        super().__init__("; ".join(errors))


def _object(value: object, path: str, errors: list[str]) -> dict[str, object] | None:
    if not isinstance(value, dict):
        errors.append(f"{path} must be an object")
        return None
    return cast("dict[str, object]", value)


def _list(value: object, path: str, errors: list[str]) -> list[object] | None:
    if not isinstance(value, list):
        errors.append(f"{path} must be a list")
        return None
    return cast("list[object]", value)


def _text(value: object, path: str, errors: list[str]) -> str | None:
    if not isinstance(value, str) or not value or any(char.isspace() for char in value):
        errors.append(f"{path} must be a non-empty string without whitespace")
        return None
    return value


def _exact_fields(value: dict[str, object], required: set[str], path: str, errors: list[str]) -> None:
    for name in sorted(required - value.keys()):
        errors.append(f"{path}.{name} is required")
    for name in sorted(value.keys() - required):
        errors.append(f"{path}.{name} is not allowed")


def validate_publication(data: object) -> dict[str, object]:
    """Return normalized publication evidence or raise every detected violation."""
    errors: list[str] = []
    state = _object(data, "publication", errors)
    if state is None:
        raise PublicationValidationError(errors)

    for name in sorted(_REQUIRED - state.keys()):
        errors.append(f"{name} is required")
    for name in sorted(state.keys() - _ALLOWED):
        errors.append(f"{name} is not allowed")

    mode = state.get("mode")
    topology = state.get("topology")
    provider = state.get("provider")
    if mode not in _MODES:
        errors.append(f"mode must be one of {', '.join(sorted(_MODES))}")
    if topology not in _TOPOLOGIES:
        errors.append(f"topology must be one of {', '.join(sorted(_TOPOLOGIES))}")
    if provider not in _PROVIDERS:
        errors.append(f"provider must be one of {', '.join(sorted(_PROVIDERS))}")

    artifacts = _list(state.get("artifacts"), "artifacts", errors)
    if artifacts is not None:
        for index, raw in enumerate(artifacts):
            item = _object(raw, f"artifacts[{index}]", errors)
            if item is None:
                continue
            _exact_fields(item, {"target", "backend", "verified"}, f"artifacts[{index}]", errors)
            _ = _text(item.get("target"), f"artifacts[{index}].target", errors)
            _ = _text(item.get("backend"), f"artifacts[{index}].backend", errors)
            if item.get("verified") is not True:
                errors.append(f"artifacts[{index}].verified must be true")

    gate = _object(state.get("gate"), "gate", errors)
    if gate is not None:
        _exact_fields(gate, {"command", "result"}, "gate", errors)
        if not isinstance(gate.get("command"), str) or not gate.get("command"):
            errors.append("gate.command must be a non-empty string")
        if gate.get("result") not in {"pass", "n/a"}:
            errors.append("gate.result must be pass or n/a")

    commits = _list(state.get("commits"), "commits", errors)
    if commits is not None:
        for index, sha in enumerate(commits):
            if not isinstance(sha, str) or _SHA.fullmatch(sha) is None:
                errors.append(f"commits[{index}] must be a 7-40 character hexadecimal SHA")

    prs = _list(state.get("prs"), "prs", errors)
    if prs is not None:
        for index, raw in enumerate(prs):
            item = _object(raw, f"prs[{index}]", errors)
            if item is None:
                continue
            _exact_fields(item, {"url", "base", "head", "verified"}, f"prs[{index}]", errors)
            url = item.get("url")
            parsed = urlparse(url) if isinstance(url, str) else None
            if parsed is None or parsed.scheme not in {"http", "https"} or not parsed.netloc:
                errors.append(f"prs[{index}].url must be an HTTP(S) URL")
            _ = _text(item.get("base"), f"prs[{index}].base", errors)
            _ = _text(item.get("head"), f"prs[{index}].head", errors)
            if item.get("verified") is not True:
                errors.append(f"prs[{index}].verified must be true")

    risk = state.get("risk")
    if not isinstance(risk, str) or not risk.strip():
        errors.append("risk must be a non-empty string")

    pr_plan = state.get("pr_plan")
    if pr_plan is not None:
        plan = _object(pr_plan, "pr_plan", errors)
        if plan is not None:
            _exact_fields(plan, {"plate_layout"}, "pr_plan", errors)
            if plan.get("plate_layout") != topology:
                errors.append("pr_plan.plate_layout must match topology")

    if mode == "topology-preflight":
        if topology not in {"single", "stacked"}:
            errors.append("topology-preflight requires single or stacked topology")
        if provider != "n/a":
            errors.append("topology-preflight requires provider n/a")
        if gate != {"command": "n/a", "result": "n/a"}:
            errors.append("topology-preflight requires gate n/a")
        if commits:
            errors.append("topology-preflight requires no commits")
        if prs:
            errors.append("topology-preflight requires no PRs")
    else:
        if gate is not None and gate.get("result") != "pass":
            errors.append("publication requires a passing gate")
        if mode == "commit-only":
            if topology != "n/a" or provider != "n/a":
                errors.append("commit-only requires topology and provider n/a")
            if commits is not None and not commits:
                errors.append("commit-only requires at least one commit")
            if prs:
                errors.append("commit-only requires no PRs")
        elif mode in {"new-pr", "existing-pr"}:
            if topology == "single" and provider != "ordinary":
                errors.append("single topology requires provider ordinary")
            if topology == "stacked" and provider not in _STACK_PROVIDERS:
                errors.append("stacked topology requires a stack provider")
            if commits is not None and not commits:
                errors.append(f"{mode} requires at least one commit")
            if prs is not None and not prs:
                errors.append(f"{mode} requires at least one verified PR")
        elif mode == "stack-maintenance":
            if topology != "stacked" or provider not in _STACK_PROVIDERS:
                errors.append("stack-maintenance requires stacked topology and a stack provider")
            if prs is not None and not prs:
                errors.append("stack-maintenance requires at least one verified PR")

    if errors:
        raise PublicationValidationError(errors)
    normalized = copy.deepcopy(state)
    return {"valid": True, **normalized}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    _ = parser.add_argument("state", type=Path)
    args = parser.parse_args(argv)
    state_path = cast(Path, args.state)
    try:
        data = cast(object, json.loads(state_path.read_text()))
        result = validate_publication(data)
    except (OSError, json.JSONDecodeError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    except PublicationValidationError as error:
        for message in error.errors:
            print(f"ERROR: {message}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
