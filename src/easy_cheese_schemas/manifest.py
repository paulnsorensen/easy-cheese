"""Run-manifest types: the durable state of an in-flight fan-out run.

The manifest at `.cheese/ultracook/<slug>/manifest.yaml` is the only record a
`--resume` has of where a crashed run stopped, so a reader must be able to tell
a coherent manifest from a truncated or hand-edited one *before* it acts on
it. These types carry the shape src/fanout/validate_manifest.py enforces today,
with each field's rule attached to the field rather than restated at every
reader.

The curd record here is the *run-manifest* entity: the decomposed curd plus
its dispatch lifecycle (id / status / retry_count). It is a different concept
from the spec-level curd block in `curd.py`, and the two deliberately do not
share field names or types.
"""

from __future__ import annotations

import graphlib
import re
from collections.abc import Sequence
from enum import Enum
from typing import Any

from attrs import Attribute, define, field, validators

from easy_cheese_schemas.pr_plan import PrPlan

_OID_RE = re.compile(r"(?:[0-9A-Fa-f]{40}|[0-9A-Fa-f]{64})")
_DIFF_HASH_RE = re.compile(r"sha256:[0-9A-Fa-f]{64}")
_WIRING_ID_RE = re.compile(r"^W[0-9]+$")
# A behaviour sentence joining two distinct verbs with "and" usually means the
# curd should be split. Intentionally permissive -- "X and Y" (no second verb)
# is fine.
_TWO_VERB_AND = re.compile(
    r"\b(adds|extracts|renames|fixes|removes|updates|implements|creates|deletes"
    r"|wires|registers|exposes|replaces)\b"
    r".*?\band\b\s+"
    r"\b(adds|extracts|renames|fixes|removes|updates|implements|creates|deletes"
    r"|wires|registers|exposes|replaces)\b",
    re.IGNORECASE,
)
_COMMAND_CHAIN = ("&&", "||", ";")

# Exactly one number governs the linear/parallel split (src/fanout/mode.py).
# It lives here rather than in decomposition.py because the run manifest owns
# the same curd collection and enforces the same rule over it.
PARALLEL_THRESHOLD = 2

__all__ = [
    "PARALLEL_THRESHOLD",
    "AgentAttempt",
    "AgentRequest",
    "AgentResolution",
    "AttemptResult",
    "Baseline",
    "BaselineGate",
    "CurdRecord",
    "DecomposedCurd",
    "Effort",
    "GateFailure",
    "Isolation",
    "PermissionEnforcement",
    "Permissions",
    "Phase",
    "PlateLayout",
    "PostReview",
    "Power",
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
]


class Phase(str, Enum):
    """Latest completed phase; `--resume` picks up at the next one."""

    GATE_APPROVED = "gate_approved"
    SEED_COMPLETE = "seed_complete"
    CURDS_COMPLETE = "curds_complete"
    MERGE_COMPLETE = "merge_complete"
    WIRING_COMPLETE = "wiring_complete"
    FINAL_MERGE_COMPLETE = "final_merge_complete"
    POST_REVIEW_COMPLETE = "post_review_complete"
    PR_PUBLISH_COMPLETE = "pr_publish_complete"


class SeedStatus(str, Enum):
    """Seed work never runs concurrently, so it has no `running` state."""

    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"


class WorkStatus(str, Enum):
    """Lifecycle of a dispatched unit of work -- a curd or a wiring row."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class WiringType(str, Enum):
    BARREL_EXPORT = "barrel_export"
    DI_REGISTRATION = "di_registration"
    ROUTE_WIRING = "route_wiring"
    EVENT_SUBSCRIPTION = "event_subscription"
    CONFIG_ENTRY = "config_entry"


class Power(str, Enum):
    """Model tier an agent request demands."""

    CHEAP = "cheap"
    DEFAULT = "default"
    POWERFUL = "powerful"


class ResolvedPower(str, Enum):
    """Tier actually obtained. `UNKNOWN` marks a host that would not say."""

    CHEAP = "cheap"
    DEFAULT = "default"
    POWERFUL = "powerful"
    UNKNOWN = "unknown"


class Effort(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class Topology(str, Enum):
    INLINE = "inline"
    SEQUENTIAL = "sequential"
    PARALLEL = "parallel"
    FAN_OUT_FAN_IN = "fan-out-fan-in"


class Permissions(str, Enum):
    READ_ONLY = "read-only"
    WRITE = "write"


class Isolation(str, Enum):
    NONE = "none"
    FRESH_CONTEXT = "fresh-context"
    ISOLATED_WORKTREE = "isolated-worktree"


class AttemptResult(str, Enum):
    ACCEPTED = "accepted"
    REJECTED = "rejected"


class PermissionEnforcement(str, Enum):
    """How the host actually confines the agent. `PROMPT_ONLY` is a degraded
    mode: the confinement is a sentence in the prompt, not a tool restriction."""

    TOOL_RESTRICTED = "tool-restricted"
    PROMPT_ONLY = "prompt-only"


class PlateLayout(str, Enum):
    SINGLE = "single"
    STACKED = "stacked"


def _non_empty_string(_instance: object, attribute: Attribute[Any], value: object) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{attribute.name} must be a non-empty string")


def _string_list(_instance: object, attribute: Attribute[Any], value: object) -> None:
    if not isinstance(value, list):
        raise ValueError(f"{attribute.name} must be a list")
    for index, item in enumerate(value, start=1):
        if not isinstance(item, str) or not item.strip():
            raise ValueError(f"{attribute.name}[{index}] must be a non-empty string")


def _non_empty_string_list(
    instance: object, attribute: Attribute[Any], value: object
) -> None:
    _string_list(instance, attribute, value)
    if not value:
        raise ValueError(f"{attribute.name} must be a non-empty list")


def _hex_oid(_instance: object, attribute: Attribute[Any], value: object) -> None:
    if not isinstance(value, str) or _OID_RE.fullmatch(value) is None:
        raise ValueError(
            f"{attribute.name} must be exactly 40 or 64 hexadecimal characters"
        )


def _diff_hash(_instance: object, attribute: Attribute[Any], value: object) -> None:
    if not isinstance(value, str) or _DIFF_HASH_RE.fullmatch(value) is None:
        raise ValueError(
            f"{attribute.name} must be sha256: followed by 64 hexadecimal characters"
        )


def _wiring_id(_instance: object, attribute: Attribute[Any], value: object) -> None:
    if not isinstance(value, str) or _WIRING_ID_RE.match(value) is None:
        raise ValueError(f"{attribute.name} must match W<number>")


def _one_behaviour(instance: object, attribute: Attribute[Any], value: object) -> None:
    _non_empty_string(instance, attribute, value)
    if _TWO_VERB_AND.search(str(value)):
        raise ValueError(
            f"{attribute.name} joins two verbs with 'and' ({value!r}) "
            "-- split into two curds"
        )


def _single_command(instance: object, attribute: Attribute[Any], value: object) -> None:
    _non_empty_string(instance, attribute, value)
    if any(token in str(value) for token in _COMMAND_CHAIN):
        raise ValueError(
            f"{attribute.name} chains multiple commands ({value!r}) -- split the curd"
        )


def reject_shared_curd_files(curds: Sequence[DecomposedCurd]) -> None:
    """Two curds that can touch the same file cannot fan out in parallel.

    A run-manifest curd is named by its `id`; a decomposition curd has no id
    until a run exists, so it is named by its 1-based position.
    """
    owner: dict[str, object] = {}
    for position, curd in enumerate(curds, start=1):
        name = getattr(curd, "id", position)
        for path in curd.files:
            if path in owner:
                raise ValueError(
                    f"file {path!r} appears in curd {owner[path]} and curd "
                    f"{name} -- curds must be file-disjoint (move shared "
                    "content to seed or wiring)"
                )
            owner[path] = name


def reject_unschedulable_wiring(wiring: Sequence[WiringRow]) -> None:
    """Wiring rows are applied in dependency order, so the graph must be
    acyclic and every W<n> dependency must exist. Dependencies outside the
    wiring set -- typically curd ids -- are legitimate and ignored, matching
    src/fanout/wiring.py."""
    ids = {row.id for row in wiring}
    errors = [
        f"wiring {row.id}: depends_on references unknown id {dependency!r}"
        for row in wiring
        for dependency in row.depends_on
        if _WIRING_ID_RE.match(dependency) and dependency not in ids
    ]
    sorter: graphlib.TopologicalSorter[str] = graphlib.TopologicalSorter()
    for row in wiring:
        sorter.add(row.id, *(d for d in row.depends_on if d in ids))
    try:
        sorter.prepare()
    except graphlib.CycleError as exc:
        path = " -> ".join(str(node) for node in exc.args[1])
        errors.append(f"wiring DAG has cycle: {path}")
    if errors:
        raise ValueError("; ".join(errors))


@define(frozen=True)
class ReviewContext:
    """Exactly what a reviewer looked at, pinned so a later reader can prove a
    finding still applies. `reviewed_tree_oid` is a tree object -- it captures
    uncommitted state, which a head commit cannot."""

    base_commit: str = field(validator=_hex_oid)
    reviewed_tree_oid: str = field(validator=_hex_oid)
    diff_hash: str = field(validator=_diff_hash)
    scope: list[str] = field(validator=_non_empty_string_list)


@define(frozen=True)
class SeedItem:
    """One shared interface written before any curd fans out."""

    description: str = field(validator=_non_empty_string)
    files: list[str] = field(validator=_non_empty_string_list)
    status: SeedStatus
    commit_sha: str | None = None


@define(frozen=True)
class Seed:
    items: list[SeedItem]


@define(frozen=True)
class DecomposedCurd:
    """A curd as a decomposition describes it: one behaviour, one acceptance
    criterion, one test target, and the files it may touch.

    A decomposition is written before any run exists, so it carries no dispatch
    lifecycle. src/fanout/curd.py draws the same line -- `behaviour_errors`
    runs at every pipeline stage, `lifecycle_errors` (id / status /
    retry_count) only for a run manifest.
    """

    behavior: str = field(validator=_one_behaviour)
    acceptance_criterion: str = field(validator=_non_empty_string)
    files: list[str] = field(validator=_non_empty_string_list)
    test_target: str = field(validator=_single_command)


@define(frozen=True)
class CurdRecord(DecomposedCurd):
    """A decomposed curd once a run manifest is tracking its dispatch: the same
    content plus the lifecycle state a `--resume` reads."""

    id: int = field(validator=validators.ge(1))
    status: WorkStatus
    # One retry, never more: a second failure is a decomposition problem, not a
    # flake.
    retry_count: int = field(validator=[validators.ge(0), validators.le(1)])
    worktree_path: str | None = None
    branch: str | None = None
    commit_sha: str | None = None
    error: str | None = None
    review_context: ReviewContext | None = None


@define(frozen=True)
class WiringRow:
    """One integration edit -- the connective work curds are forbidden to do,
    applied after their merge in dependency order."""

    id: str = field(validator=_wiring_id)
    type: WiringType
    file: str = field(validator=_non_empty_string)
    depends_on: list[str] = field(validator=_string_list)
    status: WorkStatus
    commit_sha: str | None = None


@define(frozen=True)
class AgentRequest:
    """What the orchestrator asked for before any host substitution."""

    work: str = field(validator=_non_empty_string)
    preferred_types: list[str] = field(validator=_non_empty_string_list)
    required_tools: list[str] = field(validator=_non_empty_string_list)
    permissions: Permissions
    isolation: Isolation
    minimum_power: Power
    effort: Effort


@define(frozen=True)
class AgentAttempt:
    """One resolution attempt and why it was taken or refused."""

    type: str = field(validator=_non_empty_string)
    model: str = field(validator=_non_empty_string)
    power: ResolvedPower
    result: AttemptResult
    reason: str = field(validator=_non_empty_string)


@define(frozen=True)
class ResolvedAgent:
    """The agent the run actually got."""

    type: str = field(validator=_non_empty_string)
    model: str = field(validator=_non_empty_string)
    power: ResolvedPower
    effort: Effort
    topology: Topology


@define(frozen=True)
class AgentResolution:
    """The audit trail from request to resolved agent. `degraded` records that
    the run settled for less than it asked for, which downstream readers use to
    discount the result."""

    request: AgentRequest
    attempts: list[AgentAttempt] = field(validator=validators.min_len(1))
    resolved: ResolvedAgent
    # Null exactly when the first preferred agent type was accepted.
    fallback_reason: str | None
    degraded: bool = field(validator=validators.instance_of(bool))
    permission_enforcement: PermissionEnforcement


@define(frozen=True)
class GateFailure:
    """A test that was already failing before the run touched anything."""

    suite: str = field(validator=_non_empty_string)
    test_id: str = field(validator=_non_empty_string)
    signature: str = field(validator=_non_empty_string)


@define(frozen=True)
class BaselineGate:
    cmd: str = field(validator=_non_empty_string)
    failures: list[GateFailure]


@define(frozen=True)
class RepairDispatch:
    """Where the pre-existing failures were sent to be fixed separately."""

    slug: str = field(validator=_non_empty_string)
    branch: str = field(validator=_non_empty_string)
    pr: str | None = None


@define(frozen=True)
class Baseline:
    """Gate state captured before the run, so a red gate afterwards can be
    attributed rather than blamed on the run by default."""

    captured_at: str = field(validator=_non_empty_string)
    gates: list[BaselineGate]
    repair_dispatch: RepairDispatch | None = None


@define(frozen=True)
class PostReview:
    """What the review pass looked at and how many findings it closed."""

    review_context: ReviewContext
    press_slug: str | None = None
    age_slug: str | None = None
    cure_slug: str | None = None
    findings_applied: int | None = field(
        default=None, validator=validators.optional(validators.ge(0))
    )
    findings_deferred: int | None = field(
        default=None, validator=validators.optional(validators.ge(0))
    )


@define(frozen=True)
class RunManifest:
    """One fan-out run, from gate approval to published pull requests."""

    slug: str = field(validator=_non_empty_string)
    spec_path: str = field(validator=_non_empty_string)
    created: str = field(validator=_non_empty_string)
    phase: Phase = field()
    quality_gates: list[str] = field(validator=_non_empty_string_list)
    host_capabilities: dict[str, bool] = field()
    agent_resolution: AgentResolution = field()
    seed: Seed = field()
    curds: list[CurdRecord] = field()
    wiring: list[WiringRow] = field()
    plate_layout: PlateLayout | None = None
    current_review: ReviewContext | None = None
    post_review: PostReview | None = None
    baseline: Baseline | None = None
    pr_plan: PrPlan | None = None
    phase_summary: str | None = None
    carry_forward: list[str] = field(factory=list, validator=_string_list)

    def __attrs_post_init__(self) -> None:
        # The collection rules the fan-out validator ends with: a manifest that
        # passes every field rule can still describe an undispatchable run.
        if len(self.curds) >= PARALLEL_THRESHOLD:
            reject_shared_curd_files(self.curds)
        reject_unschedulable_wiring(self.wiring)
