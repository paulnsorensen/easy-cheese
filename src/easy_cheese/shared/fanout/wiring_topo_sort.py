#!/usr/bin/env python3
"""Topologically sort a manifest's wiring[] into ordered waves.

Each wave contains the wiring IDs whose `depends_on` (restricted to other
wiring IDs) are satisfied by prior waves. Output is grouped so the orchestrator
can dispatch each wave in parallel.
"""

from __future__ import annotations

from pathlib import Path
from typing import cast

import fromargs

from easy_cheese.shared.manifest_io import ManifestLoadError, parse_mapping
from easy_cheese_schemas.wiring_graph import WiringCycleError, compute_waves

LEAVES = ("run",)


def _load_manifest(path: Path) -> dict[str, object]:
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise fromargs.CliError(f"manifest not found: {path}") from exc
    try:
        return parse_mapping(text, str(path))
    except ManifestLoadError as exc:
        raise fromargs.CliError(str(exc)) from exc


def _extract_wiring(manifest: dict[str, object]) -> list[dict[str, object]]:
    wiring = manifest.get("wiring")
    if wiring is None:
        return []
    if not isinstance(wiring, list):
        raise fromargs.CliError("manifest.wiring must be a list")
    wiring_list = cast("list[object]", wiring)
    out: list[dict[str, object]] = []
    for index, item in enumerate(wiring_list, start=1):
        if not isinstance(item, dict):
            raise fromargs.CliError(f"wiring[{index}] must be an object")
        item_dict = cast("dict[str, object]", item)
        if "id" not in item_dict:
            raise fromargs.CliError(f"wiring[{index}].id is required")
        out.append(item_dict)
    return out


def run(*, manifest: str) -> dict[str, list[list[str]]]:
    """Topologically sort a manifest's wiring[] into ordered waves.

    Parameters
    ----------
    manifest
        Path to manifest.yaml or .json.
    """
    loaded = _load_manifest(Path(manifest))
    wiring = _extract_wiring(loaded)
    try:
        waves = compute_waves(
            (str(item["id"]), cast("list[str]", item.get("depends_on", []))) for item in wiring
        )
    except WiringCycleError as exc:
        raise fromargs.CliError(f"cycle detected: {', '.join(exc.cycle_ids)}") from exc
    return {"waves": waves}


def build_app() -> fromargs.App:
    return fromargs.App(
        "wiring_topo_sort",
        help="Topologically sort a manifest's wiring[] into ordered waves.",
        help_formatter="plain",
        default_command=run,
    )


def main(argv: list[str] | None = None) -> int:
    return build_app().run(argv)


if __name__ == "__main__":
    raise SystemExit(main())
