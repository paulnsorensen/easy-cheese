"""Published Mold-to-Cook handoff schema contracts."""

from .contracts import (
    HandoffPointer,
    NormalizationAction,
    NormalizationReceipt,
    NormalizationVersion,
)

HANDOFF_SCHEMA_URI = "https://schemas.easy-cheese.dev/handoff"
NORMALIZATION_RECEIPT_SCHEMA_URI = (
    "https://schemas.easy-cheese.dev/normalization-receipt"
)
LEGACY_SCHEMA_URI = "https://schemas.easy-cheese.dev/legacy-handoff"

__all__ = [
    "HANDOFF_SCHEMA_URI",
    "LEGACY_SCHEMA_URI",
    "NORMALIZATION_RECEIPT_SCHEMA_URI",
    "HandoffPointer",
    "NormalizationAction",
    "NormalizationReceipt",
    "NormalizationVersion",
]
