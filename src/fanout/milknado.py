#!/usr/bin/env python3
"""Probe the milknado engine seam for /ultracook parallel mode.

Three roles, keyed on which milknado MCP tools are present in the agent's
toolset:

- ``engine``  — ``todo_claim`` + ``node_verify`` present: milknado owns the DAG,
  per-node worktrees, and verify-until-green; /ultracook spawns the agent per
  claimed node.
- ``tracker`` — only ``todo_add`` present: milknado records curd status but does
  not run curds; native fan-out executes and milknado just tracks.
- ``None``    — no milknado tools: native fan-out, and curds self-verify by
  running the project gates in-worker.

Detection is instruction-level per ``shared/optional-plugins.md`` — the agent
knows its own toolset; this helper only classifies a list of tool names into a
role. The list is passed in (or read from the ``EC_MCP_TOOLS`` env var); when it
is absent the probe returns ``None`` and parallel mode degrades to native
fan-out, so milknado is never a hard dependency.
"""
from __future__ import annotations

import argparse
import os

# cli is co-staged in the bundled .pyz alongside this module
import cli

# Capability tokens — substrings that identify a milknado tool regardless of the
# harness's ``mcp__milknado__`` prefixing.
ENGINE_TOOLS = ("milknado_todo_claim", "milknado_node_verify")
TRACKER_TOOL = "milknado_todo_add"

TOOLS_ENV = "EC_MCP_TOOLS"


def _has(tools: list[str], token: str) -> bool:
    return any(token in name for name in tools)


def _split(raw: str) -> list[str]:
    return [t for t in raw.replace(",", " ").split() if t]


def _tools_from_env() -> list[str]:
    return _split(os.environ.get(TOOLS_ENV, ""))


def probe(tools=None) -> str | None:
    """Classify the milknado seam from the available tool names.

    Returns ``"engine"``, ``"tracker"``, or ``None``. ``tools`` is an iterable of
    tool names; when ``None`` it is read from the ``EC_MCP_TOOLS`` env var
    (whitespace/comma separated), defaulting to empty — which yields ``None``."""
    tools = list(_tools_from_env() if tools is None else tools)
    if all(_has(tools, token) for token in ENGINE_TOOLS):
        return "engine"
    if _has(tools, TRACKER_TOOL):
        return "tracker"
    return None


def _cmd_probe(args: argparse.Namespace) -> None:
    tools = _split(args.tools) if args.tools is not None else None
    role = probe(tools)
    cli.emit("none" if role is None else role, json_mode=args.json_mode)


def _setup(parser: argparse.ArgumentParser) -> None:
    parser.description = "Probe the milknado seam (engine | tracker | none)."
    parser.add_argument(
        "--tools",
        default=None,
        help=(
            "Comma/space-separated available tool names. When omitted, read "
            f"from the {TOOLS_ENV} env var (empty → none)."
        ),
    )
    parser.set_defaults(func=_cmd_probe)


if __name__ == "__main__":
    cli.run(_setup)
