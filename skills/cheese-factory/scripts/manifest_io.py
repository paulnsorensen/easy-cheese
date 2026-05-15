"""Shared YAML/JSON loading helpers for cheese-factory scripts."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


class ManifestLoadError(Exception):
    """Raised when a manifest-like document cannot be loaded as a mapping."""


def parse_mapping(text: str, source: str = "<stdin>") -> dict[str, Any]:
    """Parse JSON first, then YAML, and require a top-level mapping."""
    try:
        data = json.loads(text)
    except json.JSONDecodeError as json_exc:
        try:
            import yaml
        except ImportError as exc:
            raise ManifestLoadError(
                f"{source}: invalid JSON and PyYAML is not installed for YAML input: {json_exc}"
            ) from exc
        try:
            data = yaml.safe_load(text)
        except yaml.YAMLError as yaml_exc:
            raise ManifestLoadError(
                f"{source}: invalid JSON ({json_exc}) and invalid YAML ({yaml_exc})"
            ) from yaml_exc

    if not isinstance(data, dict):
        raise ManifestLoadError(f"{source}: expected a mapping at document root")
    return data


def read_mapping_arg_or_stdin(argv: list[str], usage: str) -> dict[str, Any]:
    """Read one optional path argument or stdin, returning a parsed mapping."""
    if len(argv) > 2:
        raise ManifestLoadError(usage)
    if len(argv) == 2:
        path = Path(argv[1])
        try:
            text = path.read_text(encoding="utf-8")
        except FileNotFoundError as exc:
            raise ManifestLoadError(f"manifest not found: {path}") from exc
        return parse_mapping(text, str(path))
    return parse_mapping(sys.stdin.read())
