#!/usr/bin/env python3
"""Mold's strict applicability, contract, and fork-coherence taste gate.

This module is deliberately stdlib-only: the Mold bundle validates the approved
spec boundary before any downstream phase is allowed to decompose it.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

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
UI_SURFACES = frozenset({"browser", "non-browser", "not-applicable"})
NEW_MOLD_SOURCES = frozenset({"agent-mini-spec", "mold-handshake"})
BROWSER_MARKER = re.compile(
    r"\b(?:browser|e2e|end[- ]to[- ]end|playwright|cypress|selenium|webdriver|puppeteer)\b",
    re.I,
)

REFLECTIONS = ("approach", "interface", "acceptance", "test-contract")
_REFLECTION_ALIASES = {
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
        self.problems = tuple(problems) or (message,)
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
            if not isinstance(value, str) or not value.strip():
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
            not isinstance(self.interface_version, str)
            or not self.interface_version.strip()
        ):
            raise ApplicabilityError(
                f"contract-interface-version-empty:{self.acceptance_id}"
            )
        if any(not isinstance(row, str) or not row.strip() for row in self.matrix_rows):
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

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
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
        if not isinstance(self.reason, str) or not self.reason.strip():
            raise ApplicabilityError("not-applicable-reason-required")
        if self.contracts:
            raise ApplicabilityError("not-applicable-cannot-carry-test-contracts")


GateApplicability = RedRequired | NotApplicable


@dataclass(frozen=True)
class ForkCoverage:
    id: str
    decision: Any
    reflected_in: tuple[str, ...]

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "ForkCoverage":
        required = {"id", "decision", "reflected_in"}
        keys = set(value)
        missing = sorted(required - keys)
        extra = sorted(keys - required)
        if missing or extra:
            bits = []
            if missing:
                bits.append("missing=" + ",".join(missing))
            if extra:
                bits.append("unexpected=" + ",".join(extra))
            raise TasteTestError("invalid-fork-shape:" + ";".join(bits))
        fork_id = value["id"]
        if not isinstance(fork_id, str) or not fork_id.strip():
            raise TasteTestError("fork-id-empty")
        reflected = value["reflected_in"]
        if not isinstance(reflected, list) or any(
            not isinstance(item, str) for item in reflected
        ):
            raise TasteTestError(f"fork-reflected-in-not-list:{fork_id}")
        normalized: list[str] = []
        for item in reflected:
            key = _REFLECTION_ALIASES.get(item.strip().lower())
            if key is None:
                raise TasteTestError(f"fork-invalid-reflection:{fork_id}:{item}")
            if key in normalized:
                raise TasteTestError(f"fork-duplicate-reflection:{fork_id}:{key}")
            normalized.append(key)
        return cls(fork_id, value["decision"], tuple(normalized))

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "decision": copy.deepcopy(self.decision),
            "reflected_in": list(self.reflected_in),
        }


@dataclass(frozen=True)
class ForkDecision:
    id: str
    decision: Any
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

    _FIELDS = frozenset(
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
    def from_mapping(cls, value: Any) -> "ForkTasteVerdict":
        if not isinstance(value, Mapping):
            raise TasteTestError("verdict-must-be-object")
        missing = sorted(cls._FIELDS - set(value))
        extra = sorted(set(value) - cls._FIELDS)
        if missing or extra:
            bits = []
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
        raw_forks = value["forks"]
        if not isinstance(raw_forks, list):
            raise TasteTestError("verdict-forks-not-list")
        forks = tuple(
            ForkCoverage.from_mapping(item)
            if isinstance(item, Mapping)
            else (_raise("fork-must-be-object"))
            for item in raw_forks
        )
        lists: dict[str, tuple[str, ...]] = {}
        for name in (
            "contradictions",
            "orphaned_decisions",
            "unsupported_assumptions",
            "acceptance_gaps",
        ):
            raw = value[name]
            if not isinstance(raw, list) or any(
                not isinstance(item, str) or not item.strip() for item in raw
            ):
                raise TasteTestError(f"verdict-{name}-must-be-list-of-strings")
            lists[name] = tuple(item.strip() for item in raw)
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
            r"missing-section|unreflected-decision|missing-fork):([^:]+)"
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

    def to_dict(self) -> dict[str, Any]:
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


def _raise(message: str) -> Any:
    raise TasteTestError(message)


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _draft_bytes(draft: Any) -> bytes:
    if isinstance(draft, Path):
        return draft.read_bytes()
    if isinstance(draft, bytes):
        return draft
    if isinstance(draft, str):
        return draft.encode("utf-8")
    return _canonical(draft).encode("utf-8")


def draft_sha256(draft: Any) -> str:
    return hashlib.sha256(_draft_bytes(draft)).hexdigest()


def _spec_text(spec: Any) -> tuple[str, Mapping[str, Any]]:
    if isinstance(spec, Path):
        text = spec.read_text(encoding="utf-8")
        return text, {}
    if isinstance(spec, Mapping):
        return _canonical(spec), spec
    if isinstance(spec, bytes):
        return spec.decode("utf-8"), {}
    if not isinstance(spec, str):
        raise ApplicabilityError("spec-must-be-text-or-object")
    try:
        parsed = json.loads(spec)
    except json.JSONDecodeError:
        return spec, {}
    if isinstance(parsed, Mapping):
        return spec, parsed
    return spec, {}


def _frontmatter(text: str) -> dict[str, Any]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    try:
        end = next(i for i in range(1, len(lines)) if lines[i].strip() == "---")
    except StopIteration:
        return {}
    result: dict[str, Any] = {}
    current: dict[str, Any] | None = None
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


def is_new_mold_spec(spec: Any) -> bool:
    """Return whether ``spec`` came through Mold's marked production path."""
    text, raw_spec = _spec_text(spec)
    front = _frontmatter(text)
    source = raw_spec.get("source", front.get("source"))
    return source in NEW_MOLD_SOURCES


def _scalar(value: str) -> Any:
    value = value.strip()
    if value in {"{}", "[]"}:
        return {} if value == "{}" else []
    if value.lower() in {"true", "false"}:
        return value.lower() == "true"
    if (value.startswith("{") and value.endswith("}")) or (
        value.startswith("[") and value.endswith("]")
    ):
        try:
            return json.loads(value.replace("'", '"'))
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


def _acceptance_ids(text: str, spec: Mapping[str, Any]) -> tuple[str, ...]:
    raw = spec.get("acceptance_ids", spec.get("acceptance"))
    if isinstance(raw, list):
        found = [
            item
            for item in (re.search(r"\bAC-\d+\b", str(value)) for value in raw)
            if item
        ]
        ids = [item.group(0) for item in found]
    else:
        body = _section(text, "Acceptance")
        ids = re.findall(r"^\s*(?:[-*]\s*)?(AC-\d+)\s*:", body, re.M)
        if not ids:
            ids = re.findall(r"\bAC-\d+\b", body)
    if len(set(ids)) != len(ids):
        raise ApplicabilityError("acceptance-ids-not-unique")
    return tuple(ids)


def _contract_items(text: str, spec: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    for key in ("test_contracts", "test_contract", "contracts"):
        value = spec.get(key)
        if value is not None:
            if not isinstance(value, list) or any(
                not isinstance(item, Mapping) for item in value
            ):
                raise ApplicabilityError("test-contracts-must-be-list-of-objects")
            return list(value)
    body = _section(text, "Test Contracts")
    rows: list[Mapping[str, Any]] = []
    for line in body.splitlines():
        if not line.strip().startswith("|") or re.match(r"^\s*\|\s*:?-+", line):
            continue
        cells = [cell.strip().strip("`") for cell in line.strip().strip("|").split("|")]
        if len(cells) < 5 or cells[0].lower() in {"acceptance", "acceptance id"}:
            continue
        row: dict[str, Any] = {
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


def _matrix_rows(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return tuple(
            row.strip().strip("`")
            for row in re.split(r"\s*(?:<br\s*/?>|[,;])\s*", value, flags=re.I)
            if row.strip().strip("`")
        )
    if isinstance(value, list) and all(isinstance(row, str) for row in value):
        return tuple(row.strip() for row in value if row.strip())
    raise ApplicabilityError(
        "test-contract-matrix-rows-must-be-list-or-delimited-string"
    )


def _has_test_contract_section(text: str, spec: Mapping[str, Any]) -> bool:
    return any(
        key in spec for key in ("test_contracts", "test_contract", "contracts")
    ) or bool(re.search(r"(?im)^#{1,6}\s+Test Contracts\s*$", text))


def parse_test_contracts(spec: Any) -> tuple[TestContract, ...]:
    text, raw_spec = _spec_text(spec)
    front = _frontmatter(text)
    source = {**front, **raw_spec}
    items = _contract_items(text, source)
    contracts: list[TestContract] = []
    for item in items:
        acceptance_value = item.get("acceptance_id", item.get("acceptance", ""))
        interface_value = item.get("interface", item.get("interface_referent"))
        seam_value = item.get("seam", item.get("outermost_stable_seam"))
        ids = re.findall(r"\bAC-\d+\b", str(acceptance_value))
        if not ids:
            raise ApplicabilityError("contract-acceptance-id-missing")
        interface_version_value = item.get("interface_version")
        matrix_rows_value = item.get("matrix_rows")
        for acceptance_id in ids:
            contracts.append(
                TestContract(
                    acceptance_id=acceptance_id,
                    interface=_clean_cell(interface_value),
                    seam=_clean_cell(seam_value),
                    expected_failure=_clean_cell(item.get("expected_failure")),
                    mode=_clean_cell(item.get("mode")).lower().replace("gatemode.", ""),
                    contract_source=_clean_cell(
                        item.get("contract_source", "approved")
                    ),
                    interface_version=(
                        _clean_cell(interface_version_value) or None
                        if interface_version_value is not None
                        else None
                    ),
                    matrix_rows=_matrix_rows(matrix_rows_value),
                )
            )
    ids = [contract.acceptance_id for contract in contracts]
    if len(set(ids)) != len(ids):
        raise ApplicabilityError("test-contract-acceptance-ids-not-unique")
    expected = _acceptance_ids(text, source)
    if contracts and not expected:
        raise ApplicabilityError("acceptance-ids-required")
    if set(ids) != set(expected):
        missing = sorted(set(expected) - set(ids))
        extra = sorted(set(ids) - set(expected))
        detail = ";".join(
            part
            for part in (
                "missing=" + ",".join(missing) if missing else "",
                "extra=" + ",".join(extra) if extra else "",
            )
            if part
        )
        raise ApplicabilityError("test-contract-coverage-mismatch:" + detail)
    return tuple(contracts)


def _clean_cell(value: Any) -> str:
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


def parse_gate_applicability(
    spec: Any, *, require_ui_surface: bool = False
) -> GateApplicability:
    text, raw_spec = _spec_text(spec)
    front = _frontmatter(text)
    merged = {**front, **raw_spec}
    declaration = merged.get("gate_applicability")
    if not isinstance(declaration, Mapping):
        inline = re.search(r"(?im)^gate_applicability:\s*\{([^}]*)\}\s*$", text)
        if inline:
            declaration = {
                key.strip(): value.strip().strip("'\"")
                for key, value in re.findall(r"([\w-]+)\s*:\s*([^,]+)", inline.group(1))
            }
    if not isinstance(declaration, Mapping):
        raise ApplicabilityError("gate-applicability-declaration-required")
    disposition = declaration.get("disposition")
    work_class = declaration.get("work_class")
    ui_surface = declaration.get("ui_surface")
    problems: list[str] = []
    if ui_surface is None:
        if require_ui_surface:
            problems.append("gate-applicability-ui-surface-required")
    elif not isinstance(ui_surface, str) or ui_surface not in UI_SURFACES:
        problems.append("gate-applicability-invalid-ui-surface")

    if disposition not in {"red-required", "not-applicable"}:
        problems.append("gate-applicability-invalid-disposition")

    if disposition == "red-required":
        contracts = parse_test_contracts(spec)
        if work_class != "behavior":
            problems.append("red-required-work-class-must-be-behavior")
        if not contracts:
            problems.append("red-required-needs-test-contracts")
        elif not any(
            contract.mode in EXECUTABLE_CONTRACT_MODES for contract in contracts
        ):
            problems.append(RED_REQUIRED_EXECUTABLE_PROBLEM)
        if ui_surface == "not-applicable":
            problems.append("red-required-ui-surface-must-be-browser-or-non-browser")
        if ui_surface == "browser":
            if not all(_has_browser_interface(contract) for contract in contracts):
                problems.append("browser-e2e-interface-required")
            if not all(_has_browser_seam(contract) for contract in contracts):
                problems.append("browser-e2e-seam-required")
        if problems:
            raise ApplicabilityError("; ".join(problems), problems)
        return RedRequired(
            "behavior",
            contracts,
            ui_surface=ui_surface if isinstance(ui_surface, str) else None,
        )

    reason = declaration.get("reason") or merged.get("not_applicable_reason")
    if work_class not in NON_BEHAVIOR_CLASSES:
        problems.append("not-applicable-work-class-must-be-closed-non-behavior")
    if _has_test_contract_section(text, merged):
        problems.append("not-applicable-cannot-carry-test-contracts")
    normalized_reason = reason.strip() if isinstance(reason, str) else ""
    if not normalized_reason:
        problems.append("not-applicable-reason-required")
    if ui_surface is not None and ui_surface != "not-applicable":
        problems.append("not-applicable-ui-surface-must-be-not-applicable")
    if problems:
        raise ApplicabilityError("; ".join(problems), problems)
    return NotApplicable(
        work_class,
        normalized_reason,
        ui_surface=ui_surface if isinstance(ui_surface, str) else None,
    )


def _normalize_ledger(value: Any) -> tuple[tuple[ForkDecision, ...], tuple[str, ...]]:
    if isinstance(value, Mapping):
        raw = value.get(
            "forks",
            value.get("decisions", value.get("ledger", value.get("settled_decisions"))),
        )
        if raw is None:
            raw = []
            for key, item in value.items():
                if not isinstance(key, str):
                    continue
                if isinstance(item, Mapping):
                    raw.append({"id": key, **item})
                else:
                    raw.append({"id": key, "decision": item})
    else:
        raw = value
    if not isinstance(raw, (list, tuple)):
        raise TasteTestError("decision-ledger-must-be-list")
    entries: list[ForkDecision] = []
    problems: list[str] = []
    for item in raw:
        if not isinstance(item, Mapping):
            problems.append("ledger-entry-must-be-object")
            continue
        fork_id = item.get("id")
        if not isinstance(fork_id, str) or not fork_id.strip():
            problems.append("ledger-fork-id-empty")
            continue
        status = str(item.get("status", "settled")).lower()
        settled = bool(
            item.get(
                "settled",
                status in {"settled", "decided", "approved", "closed", "done"},
            )
        )
        consequential = bool(
            item.get("consequential", item.get("impact", "consequential") != "minor")
        )
        if settled and consequential:
            entries.append(
                ForkDecision(fork_id.strip(), item.get("decision"), True, True)
            )
    ids = [entry.id for entry in entries]
    if len(set(ids)) != len(ids):
        problems.append("ledger-duplicate-fork-id")
    return tuple(entries), tuple(problems)


def _draft_sections(draft: Any) -> dict[str, str]:
    if isinstance(draft, Mapping):
        result: dict[str, str] = {}
        for key, value in draft.items():
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
            for word in re.findall(r"[a-z0-9]{3,}", needle)
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
        values[name] = list(dict.fromkeys([*values[name], *items]))
    return ForkTasteVerdict.from_mapping(values)


def _applicability_gaps(draft: Any) -> list[str]:
    try:
        parse_gate_applicability(draft, require_ui_surface=True)
    except ApplicabilityError as exc:
        if exc.problems == ("gate-applicability-declaration-required",):
            if not is_new_mold_spec(draft):
                return []
            return ["gate-applicability:gate-applicability-declaration-required"]
        return [f"gate-applicability:{problem}" for problem in exc.problems]
    return []


def taste_test(
    draft: Any,
    decision_ledger: Any,
    reviewer_verdict: Mapping[str, Any] | ForkTasteVerdict,
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
    additions: dict[str, list[str]] = {
        "contradictions": [],
        "orphaned_decisions": [],
        "unsupported_assumptions": [],
        "acceptance_gaps": [
            *ledger_problems,
            *_applicability_gaps(draft),
        ],
    }

    if candidate.draft_sha256 != draft_sha256(draft):
        additions["acceptance_gaps"].append("stale-draft-digest")
    seen: set[str] = set()
    sections = _draft_sections(draft)
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
        for location in REFLECTIONS:
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
    draft: Any,
    decision_ledger: Any,
    reviewer_verdict: Mapping[str, Any] | ForkTasteVerdict,
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
    metadata: Mapping[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "next": "cut",
            "command": list(self.command),
            "spec_ref": self.spec_ref,
            "metadata": copy.deepcopy(dict(self.metadata)),
        }


def red_required_handoff(
    spec_ref: str | Path,
    applicability: GateApplicability,
    metadata: Mapping[str, Any] | None = None,
) -> MoldHandoff:
    if not isinstance(applicability, RedRequired):
        raise ApplicabilityError("cut-handoff-requires-red-required")
    pointer = str(spec_ref)
    if not pointer.strip():
        raise TasteTestError("durable-spec-pointer-required")
    preserved = copy.deepcopy(dict(metadata or {}))
    gate_metadata = preserved.get("gate_applicability")
    if not isinstance(gate_metadata, Mapping):
        gate_metadata = {}
    else:
        gate_metadata = dict(gate_metadata)
    gate_metadata.setdefault("disposition", "red-required")
    gate_metadata.setdefault("work_class", applicability.work_class)
    if applicability.ui_surface is not None:
        gate_metadata.setdefault("ui_surface", applicability.ui_surface)
    preserved["gate_applicability"] = gate_metadata
    return MoldHandoff(pointer, ("/cut", "--auto", pointer), preserved)


def auto_handoff(
    spec_ref: str | Path,
    applicability: GateApplicability,
    metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    return red_required_handoff(spec_ref, applicability, metadata).to_dict()


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__.splitlines()[0] if __doc__ else "Mold taste gate"
    )
    parser.add_argument("--draft", type=Path, required=True)
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--verdict", type=Path, required=True)
    parser.add_argument("--correction-round", type=int, default=0)
    args = parser.parse_args(argv)
    try:
        draft = args.draft.read_bytes()
        ledger = _load_json(args.ledger)
        verdict = _load_json(args.verdict)
        result = taste_test(
            draft, ledger, verdict, correction_round=args.correction_round
        )
        print(json.dumps(result.to_dict(), sort_keys=True))
        gate = decomposition_gate(result, correction_round=args.correction_round)
        return 0 if gate.allowed else 1
    except (OSError, json.JSONDecodeError, TasteTestError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
