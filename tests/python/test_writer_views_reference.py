"""The generated writer-view reference must carry the schema's meaning.

The freshness test compares bytes. These tests compare meaning: the kind to
payload mapping, and the required or optional status of every field.
"""

from __future__ import annotations

import importlib.util
import json
import re
import sys
from pathlib import Path
from typing import cast

import pytest

ROOT = Path(__file__).resolve().parents[2]
for _extra in (ROOT / "vendor", ROOT / "src", ROOT):
    if str(_extra) not in sys.path:
        sys.path.insert(0, str(_extra))

pytestmark = pytest.mark.skipif(  # noqa: V107
    importlib.util.find_spec("attrs") is None,
    reason="runtime requirements are not installed",
)

from easy_cheese_schemas import contracts  # noqa: E402
from easy_cheese_schemas.schema_runtime import schema_bytes  # noqa: E402

from scripts import render_generated_regions as render  # noqa: E402

_TYPE_BLOCK = re.compile(r"^type (\w+) \{\n(.*?)^\}$", re.DOTALL | re.MULTILINE)
_FIELD = re.compile(r"^  (\w+)(\??) ")


def _rendered() -> str:
    return render.render_writer_views_region()


def _blocks() -> dict[str, dict[str, bool]]:
    """Type name -> field name -> whether the reference marks it optional."""
    blocks: dict[str, dict[str, bool]] = {}
    matches = cast("list[tuple[str, str]]", _TYPE_BLOCK.findall(_rendered()))
    for name, body in matches:
        fields: dict[str, bool] = {}
        for line in body.splitlines():
            match = _FIELD.match(line)
            assert match is not None, line
            fields[match.group(1)] = match.group(2) == "?"
        blocks[name] = fields
    return blocks


def test_reference_renders_the_kind_to_payload_mapping() -> None:
    """A writer resolves its payload type from the document kind."""
    rendered = _rendered()
    for kind, payload in contracts.writer_payload_types().items():
        assert f"  {cast(str, kind.value)} -> {payload.__name__}\n" in rendered


def test_reference_optional_markers_match_the_schema_required_lists() -> None:
    """An unmarked field is required; a marked field is optional."""
    schema = cast(
        "dict[str, object]", json.loads(schema_bytes(contracts.AgentWriterView))
    )
    definitions = cast("dict[str, dict[str, object]]", schema["$defs"])
    blocks = _blocks()
    assert set(definitions) <= set(blocks), set(definitions) - set(blocks)

    for name, definition in definitions.items():
        required = set(cast("list[str]", definition.get("required", [])))
        properties = set(cast("dict[str, object]", definition["properties"]))
        fields = blocks[name]
        assert set(fields) == properties, name
        optional = {field for field, marked in fields.items() if marked}
        assert optional == properties - required, name
