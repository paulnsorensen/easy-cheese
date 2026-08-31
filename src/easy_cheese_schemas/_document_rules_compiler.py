"""Build-only compiler for the marker-derived mold-spec document rules.

This module is intentionally excluded from wheels and runtime bundles.  mold.pyz
imports only the generated ``_document_rules`` projection, which is
dependency-free (stdlib-only), unlike this compiler which reaches the
attrs-decorated models in ``contracts.py``.
"""

from __future__ import annotations

import pprint
from collections.abc import Mapping, Sequence
from typing import ClassVar, Protocol, cast


class _TableRuleLike(Protocol):
    columns: Sequence[str]
    per_row: Sequence[str]


class _SectionLike(Protocol):
    name: str
    optional: bool
    table: _TableRuleLike | None


class _CrossFieldRuleLike(Protocol):
    rule_id: str
    description: str


class _DocumentContractLike(Protocol):
    slug: ClassVar[str]
    sections: ClassVar[Sequence[_SectionLike]]
    cross_field_rules: ClassVar[Sequence[_CrossFieldRuleLike]]
    enums: ClassVar[Mapping[str, Sequence[str]]]


def collect(contract: type) -> type[_DocumentContractLike]:
    """Adopt a marked document-contract class as the compiler's input.

    The class is taken bare: its ``ClassVar`` containers are invariant concrete
    ``tuple``/``dict`` types that no structural annotation here can match, so
    the shape ``render`` relies on is asserted at this seam.
    """
    return cast("type[_DocumentContractLike]", contract)


def _section_data(section: _SectionLike) -> dict[str, object]:
    table = section.table
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


def _rule_data(rule: _CrossFieldRuleLike) -> dict[str, str]:
    return {"rule_id": rule.rule_id, "description": rule.description}


def _enum_data(cls: type[_DocumentContractLike]) -> dict[str, list[str]]:
    return {name: list(values) for name, values in cls.enums.items()}


def render(cls: type[_DocumentContractLike]) -> str:
    """Render deterministic, dependency-free document-rules source for ``cls``."""
    document_rules = {
        cls.slug: {
            "sections": [_section_data(section) for section in cls.sections],
            "cross_field_rules": [
                _rule_data(rule) for rule in cls.cross_field_rules
            ],
            "enums": _enum_data(cls),
        }
    }

    return (
        '"""Generated dependency-free mold-spec document rules; edit the\n'
        + "@document_contract models in contracts.py instead.\"\"\"\n\n"
        + "from __future__ import annotations\n\n"
        + "DOCUMENT_RULES = "
        + pprint.pformat(document_rules, indent=4, sort_dicts=True, width=161)
        + "\n"
    )
