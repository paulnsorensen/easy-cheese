"""easy-cheese-schemas: the shared document and manifest schemas.

`load` structures a raw mapping into one of the artifact types here and reports
what it could not read; `Provenance` says how the payload's stamp relates to
the version this package understands. The artifact types -- run manifest,
decomposition, curd block, PR plan -- carry their own field rules, so a reader
never has to remember which checks to run before trusting a document.
"""

from __future__ import annotations

from easy_cheese_schemas.compat import (
    MIN_READABLE,
    SCHEMA_VERSION,
    Loaded,
    Provenance,
    load,
)
from easy_cheese_schemas.curd import (
    MAX_WAVE_SIZE,
    MIN_CURD_SURFACE,
    CurdBlock,
    Decomposer,
    DecomposerSource,
    PlannedCurd,
)
from easy_cheese_schemas.decomposition import PARALLEL_THRESHOLD, Decomposition
from easy_cheese_schemas.gates import Readiness, classify_readiness
from easy_cheese_schemas.io import ManifestLoadError, parse_mapping
from easy_cheese_schemas.manifest import (
    AgentAttempt,
    AgentRequest,
    AgentResolution,
    AttemptResult,
    Baseline,
    BaselineGate,
    CurdRecord,
    Effort,
    GateFailure,
    Isolation,
    Permissions,
    PermissionEnforcement,
    Phase,
    PlateLayout,
    PostReview,
    Power,
    RepairDispatch,
    ResolvedAgent,
    ResolvedPower,
    ReviewContext,
    RunManifest,
    Seed,
    SeedItem,
    SeedStatus,
    Topology,
    WiringRow,
    WiringType,
    WorkStatus,
)
from easy_cheese_schemas.pr_plan import PrGroup, PrPlan, PrShape

__version__ = "0.1.0"

__all__ = [
    "MAX_WAVE_SIZE",
    "MIN_CURD_SURFACE",
    "MIN_READABLE",
    "PARALLEL_THRESHOLD",
    "SCHEMA_VERSION",
    "AgentAttempt",
    "AgentRequest",
    "AgentResolution",
    "AttemptResult",
    "Baseline",
    "BaselineGate",
    "CurdBlock",
    "CurdRecord",
    "Decomposer",
    "DecomposerSource",
    "Decomposition",
    "Effort",
    "GateFailure",
    "Isolation",
    "Loaded",
    "ManifestLoadError",
    "PermissionEnforcement",
    "Permissions",
    "Phase",
    "PlannedCurd",
    "PlateLayout",
    "PostReview",
    "Power",
    "PrGroup",
    "PrPlan",
    "PrShape",
    "Provenance",
    "Readiness",
    "RepairDispatch",
    "ResolvedAgent",
    "ResolvedPower",
    "ReviewContext",
    "RunManifest",
    "Seed",
    "SeedItem",
    "SeedStatus",
    "Topology",
    "WiringRow",
    "WiringType",
    "WorkStatus",
    "__version__",
    "classify_readiness",
    "load",
    "parse_mapping",
]