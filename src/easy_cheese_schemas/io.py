"""Reading a manifest-shaped document off disk or a pipe.

The canonical on-disk format is YAML, but every producer in the workflow can
also emit JSON, so both are accepted and normalized to one mapping before any
schema type sees them. JSON is tried first because it is unambiguous and needs
no third-party parser; PyYAML stays an optional import so the package's only
hard dependencies remain attrs and cattrs.
"""

from __future__ import annotations

import json
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
                f"{source}: invalid JSON and PyYAML is not installed for YAML "
                f"input: {json_exc}"
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
