"""Build-only compiler for the marker-derived mold-spec document rules.

This module is intentionally excluded from wheels and runtime bundles.  mold.pyz
imports only the generated ``_document_rules`` projection, which is
dependency-free (stdlib-only), unlike this compiler which reaches the
attrs-decorated models in ``contracts.py``.
"""

from __future__ import annotations

import pprint
from types import ModuleType
from typing import Sequence


def collect(module: ModuleType) -> tuple[tuple[str, type], ...]:
    """Project marked document-contract classes into ``(slug, class)`` pairs."""
    return module._registered_document_contracts()


def _section_data(section: object) -> dict[str, object]:
    table = getattr(section, "table", None)
    table_data = None
    if table is not None:
        table_data = {
            "columns": list(table.columns),
            "per_row": list(table.per_row),
        }
    return {
        "name": section.name,
        "optional": bool(section.optional),
        "table": table_data,
    }


def _rule_data(rule: object) -> dict[str, str]:
    return {"rule_id": rule.rule_id, "description": rule.description}


def render(pairs: Sequence[tuple[str, type]]) -> str:
    """Render deterministic, dependency-free document-rules source for ``pairs``."""
    ordered = tuple(sorted(pairs, key=lambda pair: pair[0]))
    slugs = [slug for slug, _cls in ordered]
    if len(slugs) != len(set(slugs)):
        raise ValueError("document contract markers produce duplicate slugs")

    document_rules = {
        slug: {
            "sections": [_section_data(section) for section in cls.sections],
            "cross_field_rules": [
                _rule_data(rule) for rule in cls.cross_field_rules
            ],
        }
        for slug, cls in ordered
    }

    return (
        '"""Generated dependency-free mold-spec document rules; edit the\n'
        "@document_contract models in contracts.py instead.\"\"\"\n\n"
        "from __future__ import annotations\n\n"
        "DOCUMENT_RULES = "
        + pprint.pformat(document_rules, indent=4, sort_dicts=True)
        + "\n"
    )
