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
from easy_cheese_schemas.wiring_graph import WiringCycleError, compute_waves


def _load_manifest(path: Path) -> dict[str, Any]:
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise cli.CliError(f"manifest not found: {path}") from exc
    try:
        return parse_mapping(text, str(path))
    except ManifestLoadError as exc:
        raise cli.CliError(str(exc)) from exc


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
    try:
        waves = compute_waves(
            (str(item["id"]), item.get("depends_on", [])) for item in wiring
        )
    except WiringCycleError as exc:
        raise cli.CliError(f"cycle detected: {', '.join(exc.cycle_ids)}") from exc
    if args.json_mode:
        cli.emit({"waves": waves}, json_mode=True, stdout=args.stdout)
        return
    for index, wave in enumerate(waves, start=1):
        print(f"wave {index}: {', '.join(wave)}", file=args.stdout)


def _setup(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--manifest", required=True, help="path to manifest.yaml or .json")
    parser.set_defaults(func=_run)


if __name__ == "__main__":
    raise SystemExit(cli.run(_setup))
