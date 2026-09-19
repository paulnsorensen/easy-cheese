"""Dependency-free inventory of schema-bearing contract modules."""

from __future__ import annotations

__all__ = ["CONTRACT_MODULES", "DOCUMENT_RULES_TARGET"]

CONTRACT_MODULES = (
    "easy_cheese_schemas.contracts",
    "easy_cheese_schemas.pr_plan",
    "easy_cheese_schemas.mold_cook",
)

DOCUMENT_RULES_TARGET = ("easy_cheese_schemas.contracts", "MoldSpecDocument")
