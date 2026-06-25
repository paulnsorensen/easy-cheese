#!/usr/bin/env python3
"""Topologically sort a manifest's wiring[] into ordered waves.

Each wave contains the wiring IDs whose `depends_on` (restricted to other
wiring IDs) are satisfied by prior waves. Output is grouped so the orchestrator
can dispatch each wave in parallel.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any


import cli  # cli is co-staged in the bundled .pyz alongside this module
from manifest_io import ManifestLoadError, parse_mapping  # noqa: E402


def _load_manifest(path: Path) -> dict[str, Any]:
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise cli.CliError(f"manifest not found: {path}") from exc
    try:
        return parse_mapping(text, str(path))
    except ManifestLoadError as exc:
        raise cli.CliError(str(exc)) from exc


def compute_waves(wiring: list[dict[str, Any]]) -> list[list[str]]:
    """Return wiring IDs grouped into Kahn-style ready-at-the-same-time waves.

    `depends_on` entries that point outside the wiring set are ignored — they
    typically reference curds, not other wiring items.
    """
    if not wiring:
        return []
    ids: list[str] = [str(item["id"]) for item in wiring]
    id_set = set(ids)
    deps: dict[str, set[str]] = {
        str(item["id"]): {d for d in item.get("depends_on", []) if d in id_set and d != item["id"]}
        for item in wiring
    }
    remaining = dict(deps)
    waves: list[list[str]] = []
    while remaining:
        ready = sorted(wid for wid, d in remaining.items() if not d)
        if not ready:
            cycle = sorted(remaining)
            raise cli.CliError(f"cycle detected: {', '.join(cycle)}")
        waves.append(ready)
        ready_set = set(ready)
        remaining = {wid: d - ready_set for wid, d in remaining.items() if wid not in ready_set}
    return waves


def _extract_wiring(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    wiring = manifest.get("wiring")
    if wiring is None:
        return []
    if not isinstance(wiring, list):
        raise cli.CliError("manifest.wiring must be a list")
    out: list[dict[str, Any]] = []
    for index, item in enumerate(wiring, start=1):
        if not isinstance(item, dict):
            raise cli.CliError(f"wiring[{index}] must be an object")
        if "id" not in item:
            raise cli.CliError(f"wiring[{index}].id is required")
        out.append(item)
    return out


def _run(args: argparse.Namespace) -> None:
    manifest = _load_manifest(Path(args.manifest))
    wiring = _extract_wiring(manifest)
    waves = compute_waves(wiring)
    if args.json_mode:
        cli.emit({"waves": waves}, json_mode=True)
        return
    for index, wave in enumerate(waves, start=1):
        print(f"wave {index}: {', '.join(wave)}")


def _setup(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--manifest", required=True, help="path to manifest.yaml or .json")
    parser.set_defaults(func=_run)


if __name__ == "__main__":
    cli.run(_setup)
