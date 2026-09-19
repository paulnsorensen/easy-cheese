"""Cook ingress classification and evidence-driven preparation.

Cook is the consumer-owned boundary for Mold work.  This package deliberately
keeps preparation separate from execution: it classifies the request, resolves
continuity, checks durable evidence, and returns a closed
``CookPreparationResult``.  It never dispatches an agent and never treats a
status string as approval.
"""

from __future__ import annotations

from ._types import (
    ApprovalSource as ApprovalSource,
)
from ._types import (
    ClassifiedCookInput,
    CookEvidenceError,
    CookExecutionOutcome,
    CookHoldClearance,
    CookInputError,
    CookPreparationRequest,
    SetupEvidence,
)
from ._types import (
    PreparationEvidence as PreparationEvidence,
)
from ._types import (
    SetupAuthorizationSource as SetupAuthorizationSource,
)
from ._types import (
    SetupEvidenceSource as SetupEvidenceSource,
)
from .classify import classify_input
from .execute import execute_accepted_handoff
from .pipeline import prepare, resubmit
from .results import load_preparation_result, validate_preparation_result

__all__ = [
    "ClassifiedCookInput",
    "CookEvidenceError",
    "CookExecutionOutcome",
    "CookHoldClearance",
    "CookInputError",
    "CookPreparationRequest",
    "SetupEvidence",
    "classify_input",
    "execute_accepted_handoff",
    "load_preparation_result",
    "prepare",
    "resubmit",
    "validate_preparation_result",
]
