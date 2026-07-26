from __future__ import annotations

from dataclasses import fields
import json
from pathlib import Path

from skill_distill import contracts


SCHEMAS = Path(__file__).parents[3] / "tools/skill-distill/schemas"
CONTRACT_SCHEMAS = {
    "annotation-v1.schema.json": contracts.AnnotationV1,
    "behavior-harness-v1.schema.json": contracts.BehaviorHarness,
    "behavior-scorecard-v1.schema.json": contracts.BehaviorScorecard,
    "dataset-v1.schema.json": contracts.DatasetV1,
    "distillation-run-v1.schema.json": contracts.DistillationRun,
    "load-event-v1.schema.json": contracts.LoadEvent,
    "proposal-v1.schema.json": contracts.ProposalV1,
    "scores-v1.schema.json": contracts.ScoresV1,
    "token-metric-profile-v1.schema.json": contracts.TokenMetricProfile,
    "tokenizer-identity-v1.schema.json": contracts.TokenizerIdentity,
}


def _assert_schema_matches_contract(schema: dict, contract: type) -> None:
    contract_fields = {field.name for field in fields(contract)}

    if "title" in schema:
        assert schema["title"] == contract.__name__
    assert set(schema["required"]) == contract_fields
    assert set(schema["properties"]) == contract_fields
    assert schema["properties"]["schema_version"]["const"] == contract.__dataclass_fields__[  # type: ignore[attr-defined]
        "schema_version"
    ].default


def test_tracked_schemas_match_their_immutable_contracts() -> None:
    assert {path.name for path in SCHEMAS.glob("*.schema.json")} == set(CONTRACT_SCHEMAS)

    for filename, contract in CONTRACT_SCHEMAS.items():
        schema = json.loads((SCHEMAS / filename).read_text(encoding="utf-8"))
        _assert_schema_matches_contract(schema, contract)


def test_nested_dataset_and_proposal_contracts_cannot_drift() -> None:
    dataset = json.loads(
        (SCHEMAS / "dataset-v1.schema.json").read_text(encoding="utf-8")
    )
    proposal = json.loads(
        (SCHEMAS / "proposal-v1.schema.json").read_text(encoding="utf-8")
    )

    _assert_schema_matches_contract(dataset["$defs"]["pairEvidence"], contracts.PairEvidenceV1)
    _assert_schema_matches_contract(
        proposal["$defs"]["canonicalCenter"], contracts.CanonicalCenter
    )
