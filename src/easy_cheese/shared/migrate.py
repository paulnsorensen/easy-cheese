"""Exact-version migration of a persisted legacy artifact into a canonical
Mold-to-Cook handoff.

A legacy artifact is not an agent writer view: it was already persisted under
an older schema, so it gets no syntax-generous repair and no heuristic or
semantic coercion. :func:`migrate` recognizes exactly one registered
``(source_schema_uri, source_major, source_minor)`` via
``easy_cheese_schemas.compat.adapter_for``, applies its one deterministic
``convert``, and publishes the result through :func:`publish_canonical` so
route validation, idempotency, content-addressed persistence, and
pointer-last reveal are the same machinery :func:`easy_cheese.shared.
publication.publish` uses -- no duplicated reveal logic.
"""
from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import date
from pathlib import Path
from typing import cast

from easy_cheese_schemas import (
    CURD_PLAN_SCHEMA_URI,
    CanonicalArtifact,
    ContractVersion,
    IngressKind,
    LegacyAdapter,
    NormalizationReceipt,
    PublishedArtifact,
    adapter_for,
    canonical_digest,
    check_adapter_sunsets,
    register_adapter,
    supported_version_for,
    validate_contract,
)

from easy_cheese.shared.publication import publish_canonical, request_digest

__all__ = ["UnsupportedLegacySourceError", "migrate"]


class UnsupportedLegacySourceError(ValueError):
    """No exact-version adapter is registered for this legacy source.

    Lookup is exact-match only, so an off-by-one minor version is rejected
    exactly like an entirely unregistered schema URI.
    """


def migrate(
    legacy_payload: Mapping[str, object],
    *,
    source_schema_uri: str,
    source_major: str,
    source_minor: str,
    source_phase: str,
    destination_phase: str,
    operation_id: str,
    artifact_root: str | Path,
    reference_date: date | None = None,
) -> PublishedArtifact:
    """Migrate one persisted legacy artifact to a canonical published pointer.

    Requires an exact registered adapter for ``(source_schema_uri,
    source_major, source_minor)`` and a provable route from ``source_phase``
    to ``destination_phase`` for the adapter's ``target_schema_uri`` --
    :func:`publish_canonical` enforces the route the same way :func:`publish`
    does. Every registered adapter's sunset is enforced first via
    :func:`~easy_cheese_schemas.check_adapter_sunsets`, against
    ``reference_date`` (``date.today()`` if not supplied), so an expired
    adapter blocks migration even if it is not the one this call would use.
    The published :class:`~easy_cheese_schemas.NormalizationReceipt` carries
    ``ingress_kind=IngressKind.LEGACY_ARTIFACT`` with the source schema and
    version, never a heuristic guess at what changed.
    """
    check_adapter_sunsets(reference_date if reference_date is not None else date.today())
    adapter = adapter_for(source_schema_uri, source_major, source_minor)
    if adapter is None:
        raise UnsupportedLegacySourceError(
            f"no adapter registered for {source_schema_uri}@{source_major}.{source_minor}"
        )

    req_digest = request_digest(
        json.dumps(legacy_payload, sort_keys=True, ensure_ascii=False),
        {
            "operation_id": operation_id,
            "source_schema_uri": source_schema_uri,
            "source_major": source_major,
            "source_minor": source_minor,
        },
    )

    def _prepare() -> tuple[CanonicalArtifact, NormalizationReceipt | None]:
        converted = adapter.convert(legacy_payload)
        validated = validate_contract(
            converted,
            adapter.target_schema_uri,
            supported_version_for(adapter.target_schema_uri),
        )
        receipt = NormalizationReceipt(
            ingress_kind=IngressKind.LEGACY_ARTIFACT,
            normalizer_id=(
                f"easy_cheese_schemas.compat:{source_schema_uri}/"
                f"{source_major}.{source_minor}"
            ),
            source_digest=canonical_digest(legacy_payload),
            canonical_digest=canonical_digest(validated.value),
            source_schema_uri=source_schema_uri,
            source_version=ContractVersion(
                schema_uri=source_schema_uri,
                major=source_major,
                minor=source_minor,
            ),
        )
        return validated, receipt

    return publish_canonical(
        request_digest=req_digest,
        source_phase=source_phase,
        destination_phase=destination_phase,
        payload_schema_uri=adapter.target_schema_uri,
        operation_id=operation_id,
        artifact_root=artifact_root,
        prepare=_prepare,
    )


_LEGACY_CURD_PLAN_MAJOR = "0"
_LEGACY_CURD_PLAN_MINOR = "9"


def _convert_criterion(index: int, item: Mapping[str, object]) -> dict[str, object]:
    return {
        "criterion_id": f"legacy-criterion-{index}",
        "description": item["description"],
        "check": item["check"],
    }


def _convert_curd(item: Mapping[str, object]) -> dict[str, object]:
    criteria = cast("list[Mapping[str, object]]", item["criteria"])
    return {
        "curd_id": item["key"],
        "outcome": item["goal"],
        "scope": {"paths": list(cast("list[str]", item.get("paths", []))), "excluded_paths": []},
        "inputs": [],
        "outputs": list(cast("list[str]", item.get("outputs", []))),
        "dependencies": [],
        "criteria": [
            _convert_criterion(index, criterion)
            for index, criterion in enumerate(criteria, start=1)
        ],
        "lineage": {"identity_action": "new", "source_curd_ids": []},
    }


def _convert_curd_plan_v0_9(payload: Mapping[str, object]) -> dict[str, object]:
    """The 0.9 curd-plan writer view named the plan's goal ``goal`` and each
    curd by a bare ``key``/``goal``/``paths`` shape; 1.0 renamed these to
    ``objective``/``outcome``/``scope.paths`` and requires each curd to carry
    an identity lineage and a stable criterion id."""
    curds = [
        _convert_curd(cast("Mapping[str, object]", curd))
        for curd in cast("list[object]", payload["curds"])
    ]
    unsigned = {
        "contract_version": {
            "schema_uri": CURD_PLAN_SCHEMA_URI,
            "major": "1",
            "minor": "0",
        },
        "plan_id": payload["plan_id"],
        "revision": payload["revision"],
        "objective": payload["goal"],
        "curds": curds,
        "context": None,
        "parent_plan_ref": None,
    }
    digest = canonical_digest(unsigned)
    return {**unsigned, "digest": digest}


def _register_legacy_adapters() -> None:
    if (
        adapter_for(CURD_PLAN_SCHEMA_URI, _LEGACY_CURD_PLAN_MAJOR, _LEGACY_CURD_PLAN_MINOR)
        is not None
    ):
        return
    register_adapter(
        LegacyAdapter(
            source_schema_uri=CURD_PLAN_SCHEMA_URI,
            source_major=_LEGACY_CURD_PLAN_MAJOR,
            source_minor=_LEGACY_CURD_PLAN_MINOR,
            target_schema_uri=CURD_PLAN_SCHEMA_URI,
            remove_after="2027-06-01",
            convert=_convert_curd_plan_v0_9,
        )
    )


_register_legacy_adapters()
