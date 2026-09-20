"""Validation and loading for the closed CookPreparationResult contract."""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast

from easy_cheese_schemas import (
    canonical_bytes,
    require_contract_version,
    validate_contract,
)
from easy_cheese_schemas.mold_cook import CookPreparationResult
from easy_cheese_schemas.schema_runtime import ContractValidationError
from easy_cheese_schemas.validate import require_mapping

from ._types import CookEvidenceError
from .evidence import read_path


def validate_preparation_result(value: object) -> CookPreparationResult:
    """Validate one canonical preparation result through the shared schema."""

    raw = canonical_bytes(value)
    try:
        validated = validate_contract(
            raw,
            CookPreparationResult,
            require_contract_version(CookPreparationResult),
        ).value
    except (ContractValidationError, TypeError, ValueError) as exc:
        raise CookEvidenceError(f"invalid CookPreparationResult: {exc}") from exc
    if not isinstance(validated, CookPreparationResult):
        raise CookEvidenceError("validated preparation result has the wrong type")
    return validated


def load_preparation_result(path: str | Path) -> CookPreparationResult:
    """Load a standalone result or a Mold saved-not-ready envelope."""

    raw = read_path(Path(path))
    try:
        decoded = cast(object, json.loads(raw))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ContractValidationError("preparation result is not valid JSON") from exc
    value = require_mapping(decoded, "preparation result")
    if "value" in value and "digest" in value:
        value = require_mapping(value["value"], "preparation result value")
    if "preparation_result" in value:
        value = require_mapping(value["preparation_result"], "saved preparation result")
    return validate_preparation_result(value)
