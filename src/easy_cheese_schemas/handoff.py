"""Published Mold-to-Cook handoff schema models."""

from __future__ import annotations

from .contracts import (
    HandoffPointer,
    NormalizationAction,
    NormalizationReceipt,
)
from .phase_contracts import CURD_PLAN_SCHEMA_URI

WRITER_VIEW_SCHEMA_URI = "https://schemas.easy-cheese.dev/agent-writer-view"
HANDOFF_SCHEMA_URI = "https://schemas.easy-cheese.dev/handoff"
NORMALIZATION_RECEIPT_SCHEMA_URI = (
    "https://schemas.easy-cheese.dev/normalization-receipt"
)
LEGACY_SCHEMA_URI = "https://schemas.easy-cheese.dev/legacy-handoff"

__all__ = [
    "CURD_PLAN_SCHEMA_URI",
    "HANDOFF_SCHEMA_URI",
    "LEGACY_SCHEMA_URI",
    "NORMALIZATION_RECEIPT_SCHEMA_URI",
    "WRITER_VIEW_SCHEMA_URI",
    "HandoffPointer",
    "NormalizationAction",
    "NormalizationReceipt",
]
