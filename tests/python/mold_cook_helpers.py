"""Test-convenience re-export of the production approval builder.

Production code binds approvals through `easy_cheese.shared.mold_cook_handoff`.
Tests import the same builder here for a shorter, stable import path.
"""

from __future__ import annotations

from easy_cheese.shared.mold_cook_handoff import (
    bind_mold_cook_approval as bind_mold_cook_approval,
)

__all__ = ["bind_mold_cook_approval"]