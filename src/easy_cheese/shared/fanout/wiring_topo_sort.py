#!/usr/bin/env python3
"""Topologically sort a manifest's wiring[] into ordered waves.

Each wave contains the wiring IDs whose `depends_on` (restricted to other
wiring IDs) are satisfied by prior waves. Output is grouped so the orchestrator
can dispatch each wave in parallel.
"""

from __future__ import annotations

from pathlib import Path
import sys
from typing import Annotated, cast
from cyclopts import App, Parameter


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


def _run(*, manifest: str, json_mode: Annotated[bool, Parameter(name="--json")] = False) -> None:
    manifest_data = _load_manifest(Path(manifest))
    wiring = _extract_wiring(manifest_data)
    try:
        waves = compute_waves(
            (str(item["id"]), cast("list[str]", item.get("depends_on", []))) for item in wiring
        )
    except WiringCycleError as exc:
        raise cli.CliError(f"cycle detected: {', '.join(exc.cycle_ids)}") from exc
    if json_mode:
        cli.emit({"waves": waves}, json_mode=True)
        return
    for index, wave in enumerate(waves, start=1):
        print(f"wave {index}: {', '.join(wave)}")


app = App(name="wiring-topo-sort")
_ = app.default(_run)


def main(argv: list[str]) -> int:
    return cli.run(app, argv=argv)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
