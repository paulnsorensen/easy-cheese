#!/usr/bin/env python3
"""Mold's applicability, contract, and fork-coherence taste gate.

The canonical ``MoldSpecDocument`` validates Mold frontmatter and test contracts.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar, NoReturn, Protocol, cast

from easy_cheese_schemas.contracts import (
    GateApplicability as MoldGateApplicability,
    GateApplicabilityDisposition,
    GroundingOutcome,
    GroundingProbe,
    GroundingRow,
    MoldSpecDocument,
    MoldSpecFrontmatter,
    SpecConfidence,
    TestContractMode,
    TestContractRow,
    UiSurface,
    WorkClass,
)



class _GroundingRowFactory(Protocol):
    def __call__(
        self, *, probe: GroundingProbe, outcome: GroundingOutcome, evidence: str
    ) -> GroundingRow: ...


class _GateFactory(Protocol):
    def __call__(
        self,
        *,
        disposition: GateApplicabilityDisposition,
        work_class: WorkClass,
        ui_surface: UiSurface,
        reason: str | None,
    ) -> MoldGateApplicability: ...


class _TestRowFactory(Protocol):
    def __call__(
        self,
        *,
        acceptance_id: str,
        interface_referent: str,
        outermost_stable_seam: str,
        expected_failure: str,
        mode: TestContractMode,
        interface_version: str,
        matrix_rows: tuple[str, ...],
    ) -> TestContractRow: ...


class _FrontmatterFactory(Protocol):
    def __call__(
        self,
        *,
        slug: str,
        status: str,
        source: str,
        created: str,
        confidence: SpecConfidence,
        gate_applicability: MoldGateApplicability,
        gates_overridden: tuple[str, ...],
        agent_introduced_scope: tuple[str, ...],
        entity_referent_bindings: tuple[Mapping[str, object], ...],
    ) -> MoldSpecFrontmatter: ...


class _DocumentFactory(Protocol):
    def __call__(
        self,
        *,
        frontmatter: MoldSpecFrontmatter,
        acceptance_ids: tuple[str, ...],
        test_contract_rows: tuple[TestContractRow, ...],
        grounding_rows: tuple[GroundingRow, ...],
    ) -> MoldSpecDocument: ...


_grounding_row = cast(_GroundingRowFactory, cast(object, GroundingRow))
_gate = cast(_GateFactory, cast(object, MoldGateApplicability))
_test_row = cast(_TestRowFactory, cast(object, TestContractRow))
_frontmatter_model = cast(_FrontmatterFactory, cast(object, MoldSpecFrontmatter))
_document = cast(_DocumentFactory, cast(object, MoldSpecDocument))
ACCEPTANCE_ID = re.compile(r"^AC-\d+$")
DIGEST = re.compile(r"^[0-9a-fA-F]{64}$")
WORK_CLASSES = frozenset(
    {"behavior", "docs-only", "refactor-only", "test-only", "appearance-only"}
)
NON_BEHAVIOR_CLASSES = frozenset(WORK_CLASSES - {"behavior"})
CONTRACT_MODES = frozenset({"tracer", "contract-matrix", "guard"})
EXECUTABLE_CONTRACT_MODES = frozenset({"tracer", "contract-matrix"})
RED_REQUIRED_EXECUTABLE_PROBLEM = (
    "red-required-needs-executable-test-contracts"
)
NEW_MOLD_SOURCES = frozenset({"agent-mini-spec", "mold-handshake"})
BROWSER_MARKER = re.compile(
    r"\b(?:browser|e2e|end[- ]to[- ]end|playwright|cypress|selenium|webdriver|puppeteer)\b",
    re.I,
)

REFLECTIONS = ("approach", "interface", "acceptance", "test-contract")
# A `not-applicable` spec cannot contain a `Test Contracts` section.
# The other three sections contain the complete fork.
NOT_APPLICABLE_REFLECTIONS = tuple(
    location for location in REFLECTIONS if location != "test-contract"
)
# The pinned goal lives outside the reflection set: forks never reflect into it,
# but the ledger's `goal` must survive into it unchanged (goal-drift gate).
GOAL_SECTION = "problem"
_REFLECTION_ALIASES = {
    "problem": GOAL_SECTION,
    "problem statement": GOAL_SECTION,
    "goal": GOAL_SECTION,
    "approach": "approach",
    "interface": "interface",
    "interfaces": "interface",
    "interface-sketch": "interface",
    "interface-sketches": "interface",
    "acceptance": "acceptance",
    "interface sketches": "interface",
    "test contract": "test-contract",
    "test contracts": "test-contract",
    "test-contract": "test-contract",
    "test-contracts": "test-contract",
    "test_contract": "test-contract",
    "test_contracts": "test-contract",
}


class TasteTestError(ValueError):
    """A malformed or blocked Mold gate result."""

    def __init__(self, message: str, problems: Sequence[str] = ()) -> None:
        self.problems: tuple[str, ...] = tuple(problems) or (message,)
        super().__init__(message)


class ApplicabilityError(TasteTestError):
    """The declaration and Test Contracts do not form a valid combination."""


@dataclass(frozen=True)
class TestContract:
    acceptance_id: str
    interface: str
    seam: str
    expected_failure: str
    mode: str
    contract_source: str = "approved"
    interface_version: str | None = None
    matrix_rows: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        values = {
            "acceptance_id": self.acceptance_id,
            "interface": self.interface,
            "seam": self.seam,
            "expected_failure": self.expected_failure,
            "mode": self.mode,
            "contract_source": self.contract_source,
        }
        for name, value in values.items():
            if not isinstance(value, str) or not value.strip():  # pyright: ignore[reportUnnecessaryIsInstance]
                raise ApplicabilityError(f"contract-{name}-empty")
        if ACCEPTANCE_ID.fullmatch(self.acceptance_id) is None:
            raise ApplicabilityError(
                f"contract-invalid-acceptance-id:{self.acceptance_id}"
            )
        if self.mode not in CONTRACT_MODES:
            raise ApplicabilityError(f"contract-invalid-mode:{self.mode}")
        if self.contract_source not in {"approved", "inferred"}:
            raise ApplicabilityError(f"contract-invalid-source:{self.contract_source}")
        if re.search(
            r"\b(?:tbd|later|eventually|random|flaky)\b", self.expected_failure, re.I
        ):
            raise ApplicabilityError(
                f"contract-nondeterministic-witness:{self.acceptance_id}"
            )
        if self.interface_version is not None and (
            not isinstance(  # pyright: ignore[reportUnnecessaryIsInstance]
                self.interface_version, str
            )
            or not self.interface_version.strip()
        ):
            raise ApplicabilityError(
                f"contract-interface-version-empty:{self.acceptance_id}"
            )
        if any(
            not isinstance(row, str)  # pyright: ignore[reportUnnecessaryIsInstance]
            or not row.strip()
            for row in self.matrix_rows
        ):
            raise ApplicabilityError(f"contract-matrix-row-empty:{self.acceptance_id}")
        if len(set(self.matrix_rows)) != len(self.matrix_rows):
            raise ApplicabilityError(
                f"contract-matrix-rows-not-unique:{self.acceptance_id}"
            )
        if self.mode == "contract-matrix":
            if self.contract_source != "approved":
                raise ApplicabilityError(
                    f"contract-matrix-source-must-be-approved:{self.acceptance_id}"
                )
            if self.interface_version is None:
                raise ApplicabilityError(
                    f"contract-matrix-interface-version-required:{self.acceptance_id}"
                )
            if not self.matrix_rows:
                raise ApplicabilityError(
                    f"contract-matrix-rows-required:{self.acceptance_id}"
                )
        elif self.interface_version is not None or self.matrix_rows:
            raise ApplicabilityError(
                f"non-matrix-cannot-carry-matrix-metadata:{self.acceptance_id}"
            )

    def to_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "acceptance_id": self.acceptance_id,
            "interface": self.interface,
            "seam": self.seam,
            "expected_failure": self.expected_failure,
            "mode": self.mode,
            "contract_source": self.contract_source,
        }
        if self.mode == "contract-matrix":
            payload["interface_version"] = self.interface_version
            payload["matrix_rows"] = list(self.matrix_rows)
        return payload


@dataclass(frozen=True)
class RedRequired:
    work_class: str
    contracts: tuple[TestContract, ...]
    disposition: str = "red-required"
    ui_surface: str | None = None

    def __post_init__(self) -> None:
        if self.work_class != "behavior":
            raise ApplicabilityError("red-required-work-class-must-be-behavior")
        if not self.contracts:
            raise ApplicabilityError("red-required-needs-test-contracts")
        if not any(
            contract.mode in EXECUTABLE_CONTRACT_MODES for contract in self.contracts
        ):
            raise ApplicabilityError(RED_REQUIRED_EXECUTABLE_PROBLEM)


@dataclass(frozen=True)
class NotApplicable:
    work_class: str
    reason: str
    contracts: tuple[TestContract, ...] = ()
    disposition: str = "not-applicable"
    ui_surface: str | None = None

    def __post_init__(self) -> None:
        if self.work_class not in NON_BEHAVIOR_CLASSES:
            raise ApplicabilityError(
                "not-applicable-work-class-must-be-closed-non-behavior"
            )
        if not isinstance(self.reason, str) or not self.reason.strip():  # pyright: ignore[reportUnnecessaryIsInstance]
            raise ApplicabilityError("not-applicable-reason-required")
        if self.contracts:
            raise ApplicabilityError("not-applicable-cannot-carry-test-contracts")


GateApplicability = RedRequired | NotApplicable


@dataclass(frozen=True)
class ForkCoverage:
    id: str
    decision: object
    reflected_in: tuple[str, ...]

    @classmethod
    def from_mapping(cls, value: Mapping[str, object]) -> "ForkCoverage":
        required = {"id", "decision", "reflected_in"}
        keys = set(value)
        missing = sorted(required - keys)
        extra = sorted(keys - required)
        if missing or extra:
            bits: list[str] = []
            if missing:
                bits.append("missing=" + ",".join(missing))
            if extra:
                bits.append("unexpected=" + ",".join(extra))
            raise TasteTestError("invalid-fork-shape:" + ";".join(bits))
        fork_id = value["id"]
        if not isinstance(fork_id, str) or not fork_id.strip():
            raise TasteTestError("fork-id-empty")
        reflected = value["reflected_in"]
        if not isinstance(reflected, list):
            raise TasteTestError(f"fork-reflected-in-not-list:{fork_id}")
        reflected_items = cast(list[object], reflected)
        if any(not isinstance(item, str) for item in reflected_items):
            raise TasteTestError(f"fork-reflected-in-not-list:{fork_id}")
        reflected_strs = cast(list[str], reflected_items)
        normalized: list[str] = []
        for item in reflected_strs:
            key = _REFLECTION_ALIASES.get(item.strip().lower())
            if key is None:
                raise TasteTestError(f"fork-invalid-reflection:{fork_id}:{item}")
            if key in normalized:
                raise TasteTestError(f"fork-duplicate-reflection:{fork_id}:{key}")
            normalized.append(key)
        return cls(fork_id, value["decision"], tuple(normalized))

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "decision": copy.deepcopy(self.decision),
            "reflected_in": list(self.reflected_in),
        }


@dataclass(frozen=True)
class ForkDecision:
    id: str
    decision: object
    settled: bool = True
    consequential: bool = True


@dataclass(frozen=True)
class ForkTasteVerdict:
    draft_sha256: str
    verdict: str
    forks: tuple[ForkCoverage, ...]
    contradictions: tuple[str, ...]
    orphaned_decisions: tuple[str, ...]
    unsupported_assumptions: tuple[str, ...]
    acceptance_gaps: tuple[str, ...]

    _FIELDS: ClassVar[frozenset[str]] = frozenset(
        {
            "draft_sha256",
            "verdict",
            "forks",
            "contradictions",
            "orphaned_decisions",
            "unsupported_assumptions",
            "acceptance_gaps",
        }
    )

    @classmethod
    def from_mapping(cls, value: object) -> "ForkTasteVerdict":
        if not isinstance(value, Mapping):
            raise TasteTestError("verdict-must-be-object")
        value = cast(Mapping[str, object], value)
        missing = sorted(cls._FIELDS - set(value))
        extra = sorted(set(value) - cls._FIELDS)
        if missing or extra:
            bits: list[str] = []
            if missing:
                bits.append("missing=" + ",".join(missing))
            if extra:
                bits.append("unexpected=" + ",".join(extra))
            raise TasteTestError("invalid-verdict-shape:" + ";".join(bits))
        digest = value["draft_sha256"]
        if not isinstance(digest, str):
            raise TasteTestError("draft-digest-not-string")
        if digest.startswith("sha256:"):
            digest = digest[7:]
        if DIGEST.fullmatch(digest) is None:
            raise TasteTestError("draft-digest-invalid")
        verdict = value["verdict"]
        if verdict not in {"pass", "fail"}:
            raise TasteTestError("verdict-must-be-pass-or-fail")
        verdict = cast(str, verdict)
        raw_forks = value["forks"]
        if not isinstance(raw_forks, list):
            raise TasteTestError("verdict-forks-not-list")
        raw_forks_items = cast(list[object], raw_forks)
        forks = tuple(
            ForkCoverage.from_mapping(cast(Mapping[str, object], item))
            if isinstance(item, Mapping)
            else (_raise("fork-must-be-object"))
            for item in raw_forks_items
        )
        lists: dict[str, tuple[str, ...]] = {}
        for name in (
            "contradictions",
            "orphaned_decisions",
            "unsupported_assumptions",
            "acceptance_gaps",
        ):
            raw = value[name]
            if not isinstance(raw, list):
                raise TasteTestError(f"verdict-{name}-must-be-list-of-strings")
            raw_items = cast(list[object], raw)
            if any(
                not isinstance(item, str) or not item.strip() for item in raw_items
            ):
                raise TasteTestError(f"verdict-{name}-must-be-list-of-strings")
            raw_strs = cast(list[str], raw_items)
            lists[name] = tuple(item.strip() for item in raw_strs)
        ids = [fork.id for fork in forks]
        if len(set(ids)) != len(ids):
            raise TasteTestError("verdict-duplicate-fork-id")
        return cls(digest.lower(), verdict, forks, **lists)

    def __post_init__(self) -> None:
        if DIGEST.fullmatch(self.draft_sha256) is None:
            raise TasteTestError("draft-digest-invalid")
        if self.verdict not in {"pass", "fail"}:
            raise TasteTestError("verdict-must-be-pass-or-fail")

    @property
    def blockers(self) -> tuple[str, ...]:
        return (
            *self.contradictions,
            *self.orphaned_decisions,
            *self.unsupported_assumptions,
            *self.acceptance_gaps,
        )

    @property
    def passed(self) -> bool:
        return self.verdict == "pass" and not self.blockers

    @property
    def reopened_forks(self) -> tuple[str, ...]:
        """Only fork ids explicitly named by a failed verdict are reopened."""
        deterministic = re.compile(
            r"^(?:duplicate-fork|decision-mismatch|missing-reflection|"
            + r"missing-section|unreflected-decision|missing-fork):([^:]+)"
        )
        if self.verdict != "fail":
            return ()
        named: list[str] = []
        for blocker in self.blockers:
            match = deterministic.match(blocker)
            if match and match.group(1) not in named:
                named.append(match.group(1))
            for fork in self.forks:
                if (
                    re.search(
                        rf"(?<![A-Za-z0-9_-]){re.escape(fork.id)}(?![A-Za-z0-9_-])",
                        blocker,
                    )
                    and fork.id not in named
                ):
                    named.append(fork.id)
        return tuple(named)

    def to_dict(self) -> dict[str, object]:
        return {
            "draft_sha256": self.draft_sha256,
            "verdict": self.verdict,
            "forks": [fork.to_dict() for fork in self.forks],
            "contradictions": list(self.contradictions),
            "orphaned_decisions": list(self.orphaned_decisions),
            "unsupported_assumptions": list(self.unsupported_assumptions),
            "acceptance_gaps": list(self.acceptance_gaps),
        }


@dataclass(frozen=True)
class TasteGateResult:
    allowed: bool
    reopened_forks: tuple[str, ...]
    halted: bool
    reason: str


def _raise(message: str) -> NoReturn:
    raise TasteTestError(message)


def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _draft_bytes(draft: object) -> bytes:
    if isinstance(draft, Path):
        return draft.read_bytes()
    if isinstance(draft, bytes):
        return draft
    if isinstance(draft, str):
        return draft.encode("utf-8")
    return _canonical(draft).encode("utf-8")


def draft_sha256(draft: object) -> str:
    return hashlib.sha256(_draft_bytes(draft)).hexdigest()


def _spec_text(spec: object) -> tuple[str, Mapping[str, object]]:
    if isinstance(spec, Path):
        text = spec.read_text(encoding="utf-8")
        return text, {}
    if isinstance(spec, Mapping):
        spec_map = cast(Mapping[str, object], spec)
        return _canonical(spec_map), spec_map
    if isinstance(spec, bytes):
        return spec.decode("utf-8"), {}
    if not isinstance(spec, str):
        raise ApplicabilityError("spec-must-be-text-or-object")
    try:
        parsed = cast(object, json.loads(spec))
    except json.JSONDecodeError:
        return spec, {}
    if isinstance(parsed, Mapping):
        return spec, cast(Mapping[str, object], parsed)
    return spec, {}


def _frontmatter(text: str) -> dict[str, object]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    try:
        end = next(i for i in range(1, len(lines)) if lines[i].strip() == "---")
    except StopIteration:
        return {}
    result: dict[str, object] = {}
    current: dict[str, object] | None = None
    for line in lines[1:end]:
        match = re.match(r"^([A-Za-z][A-Za-z0-9_-]*):\s*(.*)$", line)
        nested = re.match(r"^\s{2,}([A-Za-z][A-Za-z0-9_-]*):\s*(.*)$", line)
        if nested and current is not None:
            current[nested.group(1)] = _scalar(nested.group(2))
        elif match:
            key, raw = match.groups()
            if raw:
                result[key] = _scalar(raw)
                current = None
            else:
                current = {}
                result[key] = current
        elif line.strip() and current is not None:
            current = None
    return result


def is_new_mold_spec(spec: object) -> bool:
    """Return whether ``spec`` came through Mold's marked production path."""
    text, raw_spec = _spec_text(spec)
    front = _frontmatter(text)
    source = raw_spec.get("source", front.get("source"))
    return source in NEW_MOLD_SOURCES


def _scalar(value: str) -> object:
    value = value.strip()
    if value in {"{}", "[]"}:
        return {} if value == "{}" else []
    if value.lower() in {"true", "false"}:
        return value.lower() == "true"
    if (value.startswith("{") and value.endswith("}")) or (
        value.startswith("[") and value.endswith("]")
    ):
        try:
            return cast(object, json.loads(value.replace("'", '"')))
        except json.JSONDecodeError:
            pass
    return value.strip("'\"")


def _section(text: str, title: str) -> str:
    title_pattern = (
        r"Acceptance(?: Criteria)?" if title == "Acceptance" else re.escape(title)
    )
    match = re.search(
        rf"(?ims)^#{{1,6}}\s+{title_pattern}\s*$((?:(?!^#{{1,6}}\s+).)*)",
        text,
    )
    return match.group(1) if match else ""


def _acceptance_ids(text: str, spec: Mapping[str, object]) -> tuple[str, ...]:
    raw = spec.get("acceptance_ids", spec.get("acceptance"))
    if isinstance(raw, list):
        raw_items = cast(list[object], raw)
        found = [
            item
            for item in (re.search(r"\bAC-\d+\b", str(value)) for value in raw_items)
            if item
        ]
        ids = [item.group(0) for item in found]
    else:
        body = _section(text, "Acceptance")
        ids = re.findall(r"^\s*(?:[-*]\s*)?(AC-\d+)\s*:", body, re.M)
        if not ids:
            ids = re.findall(r"\bAC-\d+\b", body)
    return tuple(ids)


def _contract_items(
    text: str, spec: Mapping[str, object]
) -> list[Mapping[str, object]]:
    for key in ("test_contracts", "test_contract", "contracts"):
        value = spec.get(key)
        if value is not None:
            if not isinstance(value, list):
                raise ApplicabilityError("test-contracts-must-be-list-of-objects")
            items = cast(list[object], value)
            if any(not isinstance(item, Mapping) for item in items):
                raise ApplicabilityError("test-contracts-must-be-list-of-objects")
            return cast(list[Mapping[str, object]], items)
    body = _section(text, "Test Contracts")
    rows: list[Mapping[str, object]] = []
    for line in body.splitlines():
        if not line.strip().startswith("|") or re.match(r"^\s*\|\s*:?-+", line):
            continue
        cells = [cell.strip().strip("`") for cell in line.strip().strip("|").split("|")]
        if len(cells) < 5 or cells[0].lower() in {"acceptance", "acceptance id"}:
            continue
        row: dict[str, object] = {
            "acceptance_id": cells[0],
            "interface": cells[1],
            "seam": cells[2],
            "expected_failure": cells[3],
            "mode": cells[4],
        }
        if len(cells) > 5:
            row["interface_version"] = cells[5]
        if len(cells) > 6:
            row["matrix_rows"] = cells[6]
        rows.append(row)
    return rows


def _matrix_rows(value: object) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return tuple(
            row.strip().strip("`")
            for row in re.split(r"\s*(?:<br\s*/?>|[,;])\s*", value, flags=re.I)
            if row.strip().strip("`")
        )
    if isinstance(value, list):
        rows = cast(list[object], value)
        if all(isinstance(row, str) for row in rows):
            str_rows = cast(list[str], rows)
            return tuple(row.strip() for row in str_rows if row.strip())
    raise ApplicabilityError(
        "test-contract-matrix-rows-must-be-list-or-delimited-string"
    )


def _has_test_contract_section(text: str, spec: Mapping[str, object]) -> bool:
    return any(
        key in spec for key in ("test_contracts", "test_contract", "contracts")
    ) or bool(re.search(r"(?im)^#{1,6}\s+Test Contracts\s*$", text))


def _grounding_rows(text: str, spec: Mapping[str, object]) -> tuple[GroundingRow, ...]:
    raw = spec.get("grounding_rows", spec.get("grounding"))
    items: list[Mapping[str, object]] = []
    if raw is not None:
        if not isinstance(raw, list):
            raise ApplicabilityError("grounding-must-be-list-of-objects")
        for row in cast(list[object], raw):
            if not isinstance(row, Mapping):
                raise ApplicabilityError("grounding-must-be-list-of-objects")
            items.append(cast(Mapping[str, object], row))
    else:
        for line in _section(text, "Grounding").splitlines():
            if not line.strip().startswith("|") or re.match(r"^\s*\|\s*:?-+", line):
                continue
            cells = [cell.strip().strip("`") for cell in line.strip().strip("|").split("|")]
            if len(cells) >= 3 and cells[0].lower() != "probe":
                items.append(
                    {"probe": cells[0], "outcome": cells[1], "evidence": cells[2]}
                )
    if not items:
        return tuple(
            _grounding_row(
                probe=probe,
                outcome=GroundingOutcome.UNAVAILABLE,
                evidence="Grounding validation belongs to the Mold document validator",
            )
            for probe in GroundingProbe
        )
    return tuple(
        _grounding_row(
            probe=GroundingProbe(_clean_cell(item.get("probe"))),
            outcome=GroundingOutcome(_clean_cell(item.get("outcome"))),
            evidence=_clean_cell(item.get("evidence")),
        )
        for item in items
    )


def _typed_mold_document(
    spec: object, *, require_ui_surface: bool = False
) -> tuple[MoldSpecDocument, str, Mapping[str, object]]:
    text, raw_spec = _spec_text(spec)
    merged: dict[str, object] = {**_frontmatter(text), **raw_spec}
    declaration = merged.get("gate_applicability")
    if not isinstance(declaration, Mapping):
        raise ApplicabilityError("gate-applicability-declaration-required")
    gate = cast(Mapping[str, object], declaration)
    ui_surface = gate.get("ui_surface")
    if ui_surface is None:
        if require_ui_surface:
            raise ApplicabilityError("gate-applicability-ui-surface-required")
        ui_surface = (
            "not-applicable"
            if gate.get("disposition") == "not-applicable"
            else "non-browser"
        )
    if (
        gate.get("disposition") == "not-applicable"
        and _has_test_contract_section(text, merged)
    ):
        raise ApplicabilityError("not-applicable-cannot-carry-test-contracts")
    try:
        gate_model = _gate(
            disposition=GateApplicabilityDisposition(
                _clean_cell(gate.get("disposition"))
            ),
            work_class=WorkClass(_clean_cell(gate.get("work_class"))),
            ui_surface=UiSurface(_clean_cell(ui_surface)),
            reason=cast(str | None, gate.get("reason") or merged.get("not_applicable_reason")),
        )
        rows: list[TestContractRow] = []
        for item in _contract_items(text, merged):
            ids = cast(
                list[str],
                re.findall(
                    r"\bAC-\d+\b",
                    str(item.get("acceptance_id", item.get("acceptance", ""))),
                ),
            )
            if not ids:
                raise ApplicabilityError("contract-acceptance-id-missing")
            for acceptance_id in ids:
                rows.append(
                    _test_row(
                        acceptance_id=acceptance_id,
                        interface_referent=_clean_cell(
                            item.get("interface", item.get("interface_referent"))
                        ),
                        outermost_stable_seam=_clean_cell(
                            item.get("seam", item.get("outermost_stable_seam"))
                        ),
                        expected_failure=_clean_cell(item.get("expected_failure")),
                        mode=TestContractMode(
                            _clean_cell(item.get("mode")).lower().replace(
                                "testcontractmode.", ""
                            )
                        ),
                        interface_version=(
                            _clean_cell(item.get("interface_version"))
                            if item.get("interface_version") is not None
                            else ""
                        ),
                        matrix_rows=_matrix_rows(item.get("matrix_rows")),
                    )
                )
        acceptance_ids = _acceptance_ids(text, merged)
        if rows and not acceptance_ids:
            raise ApplicabilityError("acceptance-ids-required")
        document = _document(
            frontmatter=_frontmatter_model(
                slug=cast(str, merged.get("slug", "legacy-spec")),
                status=cast(str, merged.get("status", "draft")),
                source=cast(str, merged.get("source", "legacy")),
                created=cast(str, merged.get("created", "unknown")),
                confidence=SpecConfidence(
                    cast(str, merged.get("confidence", "medium"))
                ),
                gate_applicability=gate_model,
                gates_overridden=cast(tuple[str, ...], merged.get("gates_overridden", ())),
                agent_introduced_scope=cast(
                    tuple[str, ...], merged.get("agent_introduced_scope", ())
                ),
                entity_referent_bindings=cast(
                    tuple[Mapping[str, object], ...],
                    merged.get("entity_referent_bindings", ()),
                ),
            ),
            acceptance_ids=acceptance_ids,
            test_contract_rows=tuple(rows),
            grounding_rows=_grounding_rows(text, merged),
        )
    except ApplicabilityError:
        raise
    except (TypeError, ValueError) as exc:
        message = str(exc)
        if "contract-matrix mode and requires both" in message:
            message = "contract-matrix-interface-version-required"
        elif "matrix_rows must not contain duplicate" in message:
            message = "contract-matrix-rows-not-unique"
        raise ApplicabilityError(message) from exc
    return document, text, merged


def _contracts_from_document(document: MoldSpecDocument) -> tuple[TestContract, ...]:
    return tuple(
        TestContract(
            acceptance_id=row.acceptance_id,
            interface=row.interface_referent,
            seam=row.outermost_stable_seam,
            expected_failure=row.expected_failure,
            mode=row.mode.value,
            interface_version=row.interface_version or None,
            matrix_rows=row.matrix_rows,
        )
        for row in document.test_contract_rows
    )




def _clean_cell(value: object) -> str:
    if not isinstance(value, str):
        raise ApplicabilityError("test-contract-field-not-string")
    return value.strip().strip("`")


def _has_browser_interface(contract: TestContract) -> bool:
    return contract.contract_source == "approved" and bool(
        BROWSER_MARKER.search(contract.interface)
    )


def _has_browser_seam(contract: TestContract) -> bool:
    return contract.contract_source == "approved" and bool(
        BROWSER_MARKER.search(contract.seam)
    )


def required_reflections(spec: object) -> tuple[str, ...]:
    """Return the reflection sections required for a consequential fork."""
    try:
        document, _, _ = _typed_mold_document(spec)
    except ApplicabilityError as exc:
        if exc.problems == ("gate-applicability-declaration-required",):
            return REFLECTIONS
        raise
    if (
        document.frontmatter.gate_applicability.disposition
        is GateApplicabilityDisposition.NOT_APPLICABLE
    ):
        return NOT_APPLICABLE_REFLECTIONS
    return REFLECTIONS


def parse_gate_applicability(
    spec: object, *, require_ui_surface: bool = False
) -> GateApplicability:
    document, _, merged = _typed_mold_document(
        spec, require_ui_surface=require_ui_surface
    )
    declaration = document.frontmatter.gate_applicability
    raw_declaration = cast(Mapping[str, object], merged["gate_applicability"])
    ui_surface = (
        declaration.ui_surface.value
        if raw_declaration.get("ui_surface") is not None
        else None
    )
    contracts = _contracts_from_document(document)
    if declaration.disposition is GateApplicabilityDisposition.RED_REQUIRED:
        problems: list[str] = []
        if not contracts:
            problems.append("red-required-needs-test-contracts")
        elif not any(
            contract.mode in EXECUTABLE_CONTRACT_MODES for contract in contracts
        ):
            problems.append(RED_REQUIRED_EXECUTABLE_PROBLEM)
        if declaration.ui_surface is UiSurface.BROWSER:
            if not all(_has_browser_interface(contract) for contract in contracts):
                problems.append("browser-e2e-interface-required")
            if not all(_has_browser_seam(contract) for contract in contracts):
                problems.append("browser-e2e-seam-required")
        if problems:
            raise ApplicabilityError("; ".join(problems), problems)
        return RedRequired(
            declaration.work_class.value, contracts, ui_surface=ui_surface
        )
    return NotApplicable(
        declaration.work_class.value, declaration.reason or "", ui_surface=ui_surface
    )


def _normalize_ledger(
    value: object,
) -> tuple[tuple[ForkDecision, ...], tuple[str, ...]]:
    raw: object
    if isinstance(value, Mapping):
        mapping_value = cast(Mapping[object, object], value)
        raw = mapping_value.get(
            "forks",
            mapping_value.get(
                "decisions", mapping_value.get("ledger", mapping_value.get("settled_decisions"))
            ),
        )
        if raw is None:
            raw_list: list[object] = []
            for key, item in mapping_value.items():
                if not isinstance(key, str):
                    continue
                if isinstance(item, Mapping):
                    raw_list.append({"id": key, **cast(Mapping[str, object], item)})
                else:
                    raw_list.append({"id": key, "decision": item})
            raw = raw_list
    else:
        raw = value
    if not isinstance(raw, (list, tuple)):
        raise TasteTestError("decision-ledger-must-be-list")
    raw_items = cast("list[object] | tuple[object, ...]", raw)
    entries: list[ForkDecision] = []
    problems: list[str] = []
    for item in raw_items:
        if not isinstance(item, Mapping):
            problems.append("ledger-entry-must-be-object")
            continue
        entry_map = cast(Mapping[str, object], item)
        fork_id = entry_map.get("id")
        if not isinstance(fork_id, str) or not fork_id.strip():
            problems.append("ledger-fork-id-empty")
            continue
        status = str(entry_map.get("status", "settled")).lower()
        settled = bool(
            entry_map.get(
                "settled",
                status in {"settled", "decided", "approved", "closed", "done"},
            )
        )
        consequential = bool(
            entry_map.get(
                "consequential", entry_map.get("impact", "consequential") != "minor"
            )
        )
        if settled and consequential:
            entries.append(
                ForkDecision(fork_id.strip(), entry_map.get("decision"), True, True)
            )
    ids = [entry.id for entry in entries]
    if len(set(ids)) != len(ids):
        problems.append("ledger-duplicate-fork-id")
    return tuple(entries), tuple(problems)


def _ledger_goal(value: object) -> str | None:
    """Return the ledger's pinned goal line, or None for a goal-less ledger."""
    if not isinstance(value, Mapping):
        return None
    goal = cast(Mapping[object, object], value).get("goal")
    if goal is None:
        return None
    if not isinstance(goal, str) or not goal.strip():
        raise TasteTestError("ledger-goal-empty")
    return goal.strip()


def _goal_gaps(sections: Mapping[str, str], goal: str | None) -> list[str]:
    """The pinned goal must appear in the draft's problem statement verbatim."""
    if goal is None:
        return []
    section = sections.get(GOAL_SECTION, "")
    if not section.strip():
        return [f"missing-section:goal:{GOAL_SECTION}"]
    if goal.casefold() not in " ".join(section.split()).casefold():
        return ["goal-drift"]
    return []


def _draft_sections(draft: object) -> dict[str, str]:
    if isinstance(draft, Mapping):
        draft_map = cast(Mapping[object, object], draft)
        result: dict[str, str] = {}
        for key, value in draft_map.items():
            normalized = _REFLECTION_ALIASES.get(str(key).strip().lower())
            if normalized:
                result[normalized] = _canonical(value)
        return result
    text = _draft_bytes(draft).decode("utf-8")
    headings = list(re.finditer(r"(?im)^#{1,6}\s+(.+?)\s*$", text))
    result = {}
    for index, heading in enumerate(headings):
        title = re.sub(r"[^a-z0-9 -]", "", heading.group(1).lower()).strip()
        key = next(
            (
                alias
                for alias, _ in _REFLECTION_ALIASES.items()
                if title == alias or title.startswith(alias + " ")
            ),
            None,
        )
        if key:
            normalized = _REFLECTION_ALIASES[key]
            end = (
                headings[index + 1].start() if index + 1 < len(headings) else len(text)
            )
            result[normalized] = text[heading.end() : end]
    return result


def _mentions(section: str, fork: ForkCoverage, expected: ForkDecision) -> bool:
    haystack = section.casefold()
    if fork.id.casefold() in haystack:
        return True
    decision = expected.decision
    if isinstance(decision, str):
        needle = decision.strip().casefold()
        if needle and needle in haystack:
            return True
        words = [
            word
            for word in cast(list[str], re.findall(r"[a-z0-9]{3,}", needle))
            if word not in {"the", "and", "with", "from"}
        ]
        return bool(words) and all(word in haystack for word in words)
    return _canonical(decision).casefold() in haystack


def _failed(
    candidate: ForkTasteVerdict, additions: Mapping[str, Sequence[str]]
) -> ForkTasteVerdict:
    values = candidate.to_dict()
    values["verdict"] = "fail"
    for name, items in additions.items():
        existing = cast(list[str], values[name])
        values[name] = list(dict.fromkeys([*existing, *items]))
    return ForkTasteVerdict.from_mapping(values)


def _applicability_gaps(draft: object) -> list[str]:
    try:
        _ = parse_gate_applicability(draft, require_ui_surface=True)
    except ApplicabilityError as exc:
        if exc.problems == ("gate-applicability-declaration-required",):
            if not is_new_mold_spec(draft):
                return []
            return ["gate-applicability:gate-applicability-declaration-required"]
        return [f"gate-applicability:{problem}" for problem in exc.problems]
    return []


def taste_test(
    draft: object,
    decision_ledger: object,
    reviewer_verdict: Mapping[str, object] | ForkTasteVerdict,
    *,
    correction_round: int = 0,
) -> ForkTasteVerdict:
    """Validate one fresh-context verdict against the exact draft and ledger."""
    if correction_round < 0 or correction_round > 2:
        raise TasteTestError("correction-round-out-of-range")
    candidate = (
        reviewer_verdict
        if isinstance(reviewer_verdict, ForkTasteVerdict)
        else ForkTasteVerdict.from_mapping(reviewer_verdict)
    )
    ledger, ledger_problems = _normalize_ledger(decision_ledger)
    expected = {entry.id: entry for entry in ledger}
    sections = _draft_sections(draft)
    additions: dict[str, list[str]] = {
        "contradictions": [],
        "orphaned_decisions": [],
        "unsupported_assumptions": [],
        "acceptance_gaps": [
            *ledger_problems,
            *_applicability_gaps(draft),
            *_goal_gaps(sections, _ledger_goal(decision_ledger)),
        ],
    }

    if candidate.draft_sha256 != draft_sha256(draft):
        additions["acceptance_gaps"].append("stale-draft-digest")
    seen: set[str] = set()
    required = required_reflections(draft)
    for fork in candidate.forks:
        if fork.id in seen:
            additions["orphaned_decisions"].append(f"duplicate-fork:{fork.id}")
            continue
        seen.add(fork.id)
        entry = expected.get(fork.id)
        if entry is None:
            additions["orphaned_decisions"].append(fork.id)
            continue
        if _canonical(fork.decision) != _canonical(entry.decision):
            additions["contradictions"].append(f"decision-mismatch:{fork.id}")
        for location in required:
            if location not in fork.reflected_in:
                additions["acceptance_gaps"].append(
                    f"missing-reflection:{fork.id}:{location}"
                )
        for location in fork.reflected_in:
            section = sections.get(location, "")
            if not section:
                additions["acceptance_gaps"].append(
                    f"missing-section:{fork.id}:{location}"
                )
            elif not _mentions(section, fork, entry):
                additions["acceptance_gaps"].append(
                    f"unreflected-decision:{fork.id}:{location}"
                )
    for fork_id in sorted(expected.keys() - seen):
        additions["acceptance_gaps"].append(f"missing-fork:{fork_id}")
    if candidate.verdict == "pass" and candidate.blockers:
        additions["acceptance_gaps"].append("pass-with-blockers")
    if (
        candidate.verdict == "fail"
        and not candidate.blockers
        and not any(additions.values())
    ):
        additions["acceptance_gaps"].append("fail-without-blocker")
    if any(additions.values()):
        candidate = _failed(candidate, additions)
    return candidate


def validate_fork_taste(
    draft: object,
    decision_ledger: object,
    reviewer_verdict: Mapping[str, object] | ForkTasteVerdict,
    *,
    correction_round: int = 0,
) -> ForkTasteVerdict:
    return taste_test(
        draft, decision_ledger, reviewer_verdict, correction_round=correction_round
    )


def reopen_named_forks(verdict: ForkTasteVerdict) -> tuple[str, ...]:
    return verdict.reopened_forks


def decomposition_gate(
    verdict: ForkTasteVerdict,
    *,
    correction_round: int = 0,
) -> TasteGateResult:
    if correction_round < 0 or correction_round > 2:
        raise TasteTestError("correction-round-out-of-range")
    if verdict.passed:
        return TasteGateResult(True, (), False, "fork-taste-test-passed")
    halted = correction_round >= 2
    return TasteGateResult(
        False,
        reopen_named_forks(verdict),
        halted,
        "third-failed-verdict" if halted else "reopen-named-forks",
    )


def require_decomposition(  # noqa: V103
    verdict: ForkTasteVerdict, *, correction_round: int = 0
) -> None:
    result = decomposition_gate(verdict, correction_round=correction_round)
    if not result.allowed:
        suffix = ",".join(result.reopened_forks) or "none"
        raise TasteTestError(f"{result.reason}:reopen={suffix}")


@dataclass(frozen=True)
class MoldHandoff:
    spec_ref: str
    command: tuple[str, ...]
    metadata: Mapping[str, object]

    def to_dict(self) -> dict[str, object]:
        return {
            "next": "cook",
            "command": list(self.command),
            "spec_ref": self.spec_ref,
            "metadata": copy.deepcopy(dict(self.metadata)),
        }


def red_required_handoff(
    spec_ref: str | Path,
    applicability: GateApplicability,
    metadata: Mapping[str, object] | None = None,
) -> MoldHandoff:
    if not isinstance(applicability, RedRequired):
        raise ApplicabilityError("handoff-requires-red-required")
    pointer = str(spec_ref)
    if not pointer.strip():
        raise TasteTestError("durable-spec-pointer-required")
    preserved = copy.deepcopy(dict(metadata or {}))
    gate_metadata_raw = preserved.get("gate_applicability")
    gate_metadata: dict[str, object]
    if isinstance(gate_metadata_raw, Mapping):
        gate_metadata = dict(cast(Mapping[str, object], gate_metadata_raw))
    else:
        gate_metadata = {}
    _ = gate_metadata.setdefault("disposition", "red-required")
    _ = gate_metadata.setdefault("work_class", applicability.work_class)
    if applicability.ui_surface is not None:
        _ = gate_metadata.setdefault("ui_surface", applicability.ui_surface)
    preserved["gate_applicability"] = gate_metadata
    return MoldHandoff(pointer, ("/cook", "--auto", pointer), preserved)


def auto_handoff(
    spec_ref: str | Path,
    applicability: GateApplicability,
    metadata: Mapping[str, object] | None = None,
) -> dict[str, object]:
    return red_required_handoff(spec_ref, applicability, metadata).to_dict()


def _load_json(path: Path) -> object:
    return cast(object, json.loads(path.read_text(encoding="utf-8")))


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__.splitlines()[0] if __doc__ else "Mold taste gate"
    )
    _ = parser.add_argument("--draft", type=Path, required=True)
    _ = parser.add_argument("--ledger", type=Path, required=True)
    _ = parser.add_argument("--verdict", type=Path, required=True)
    _ = parser.add_argument("--correction-round", type=int, default=0)
    args = parser.parse_args(argv)
    try:
        draft_path = cast(Path, args.draft)
        ledger_path = cast(Path, args.ledger)
        verdict_path = cast(Path, args.verdict)
        correction_round = cast(int, args.correction_round)
        draft = draft_path.read_bytes()
        ledger = _load_json(ledger_path)
        verdict = _load_json(verdict_path)
        result = taste_test(
            draft,
            ledger,
            cast("Mapping[str, object] | ForkTasteVerdict", verdict),
            correction_round=correction_round,
        )
        print(json.dumps(result.to_dict(), sort_keys=True))
        gate = decomposition_gate(result, correction_round=correction_round)
        return 0 if gate.allowed else 1
    except (OSError, json.JSONDecodeError, TasteTestError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
