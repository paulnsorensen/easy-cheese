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

from easy_cheese_schemas import (
    CanonicalArtifact,
    ContractVersion,
    IngressKind,
    NormalizationReceipt,
    PublishedArtifact,
    adapter_for,
    canonical_digest,
    check_adapter_sunsets,
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
    check_adapter_sunsets(
        reference_date if reference_date is not None else date.today()
    )
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
        source_phase=source_phase,
        destination_phase=destination_phase,
        payload_schema_uri=adapter.target_schema_uri,
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


