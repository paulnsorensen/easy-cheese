#!/usr/bin/env python3
"""Topologically sort a manifest's wiring[] into ordered waves.

Each wave contains the wiring IDs whose `depends_on` (restricted to other
wiring IDs) are satisfied by prior waves. Output is grouped so the orchestrator
can dispatch each wave in parallel.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Protocol, TextIO, cast


from easy_cheese.shared import cli
from easy_cheese.shared.manifest_io import ManifestLoadError, parse_mapping  # noqa: E402
from easy_cheese_schemas.wiring_graph import WiringCycleError, compute_waves


def _load_manifest(path: Path) -> dict[str, object]:
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise cli.CliError(f"manifest not found: {path}") from exc
    try:
        return parse_mapping(text, str(path))
    except ManifestLoadError as exc:
        raise cli.CliError(str(exc)) from exc


def _extract_wiring(manifest: dict[str, object]) -> list[dict[str, object]]:
    wiring = manifest.get("wiring")
    if wiring is None:
        return []
    if not isinstance(wiring, list):
        raise cli.CliError("manifest.wiring must be a list")
    wiring_list = cast("list[object]", wiring)
    out: list[dict[str, object]] = []
    for index, item in enumerate(wiring_list, start=1):
        if not isinstance(item, dict):
            raise cli.CliError(f"wiring[{index}] must be an object")
        item_dict = cast("dict[str, object]", item)
        if "id" not in item_dict:
            raise cli.CliError(f"wiring[{index}].id is required")
        out.append(item_dict)
    return out


class _Args(Protocol):
    manifest: str
    json_mode: bool
    stdout: TextIO


def _run(args: argparse.Namespace) -> None:
    a = cast(_Args, cast(object, args))
    manifest = _load_manifest(Path(a.manifest))
    wiring = _extract_wiring(manifest)
    try:
        waves = compute_waves(
            (str(item["id"]), cast("list[str]", item.get("depends_on", []))) for item in wiring
        )
    except WiringCycleError as exc:
        raise cli.CliError(f"cycle detected: {', '.join(exc.cycle_ids)}") from exc
    if a.json_mode:
        cli.emit({"waves": waves}, json_mode=True, stdout=a.stdout)
        return
    for index, wave in enumerate(waves, start=1):
        print(f"wave {index}: {', '.join(wave)}", file=a.stdout)


def _setup(parser: argparse.ArgumentParser) -> None:
    _ = parser.add_argument("--manifest", required=True, help="path to manifest.yaml or .json")
    parser.set_defaults(func=_run)


def main(argv: list[str]) -> int:
    return cli.run(_setup, argv=argv)


if __name__ == "__main__":
    raise SystemExit(cli.run(_setup))
