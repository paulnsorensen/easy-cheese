"""Canonical spec binding, readiness, and continuity for one preparation."""

from __future__ import annotations

import hashlib
from pathlib import Path

from easy_cheese_schemas import ArtifactRef
from easy_cheese_schemas.mold_cook import (
    CookExecutionHold,
    CookHoldKind,
    MoldCookInputKind,
)
from easy_cheese.shared.mold_cook_handoff import (
    MoldCookSpecReadiness,
    evaluate_mold_cook_spec,
)
from easy_cheese.shared.paths import artifact_path
from easy_cheese.shared.wheypoint.canonical import digest_bytes
from easy_cheese.shared.wheypoint.resolve import (
    Resolution,
    ResolutionOutcome,
    resolve,
)

from ._types import (
    ClassifiedCookInput,
    CookEvidenceError,
    CookInputError,
    CookPreparationRequest,
    PreparationFailure,
)
from .evidence import persist_bytes, read_path, resolve_ref


def resolve_spec_ref(
    source: ClassifiedCookInput,
    root: Path,
    request_id: str,
) -> tuple[ArtifactRef, str]:
    if source.kind is MoldCookInputKind.DIRECT_SPEC:
        if source.path is None:
            raise PreparationFailure(
                "missing-spec", "direct spec input must name a file"
            )
        raw = source.snapshot if source.snapshot is not None else read_path(source.path)
        path = source.path
    elif source.kind is MoldCookInputKind.TASK:
        raw = source.source.encode("utf-8")
        path = None
    elif source.kind is MoldCookInputKind.SLUG:
        candidate = _find_spec(source.source)
        if candidate is None:
            raise PreparationFailure(
                "missing-spec",
                f"spec slug {source.source!r} was not found",
            )
        try:
            raw = read_path(candidate)
        except (CookInputError, OSError, UnicodeDecodeError) as exc:
            raise PreparationFailure(
                "invalid-spec",
                f"cannot read spec {candidate!r}: {exc}",
                path=str(candidate),
            ) from exc
        path = candidate
    else:
        raise PreparationFailure(
            "missing-spec",
            "this input requires an independently supplied spec",
        )
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise PreparationFailure(
            "invalid-spec",
            f"spec is not UTF-8: {exc}",
            path=None if path is None else str(path),
        ) from exc
    return (
        persist_bytes(
            root,
            content=raw,
            artifact_id=f"{request_id}/spec",
            role="spec",
            media_type="text/markdown",
        ),
        text,
    )


def _find_spec(slug: str) -> Path | None:
    candidate = artifact_path("specs", slug)
    return candidate if candidate.is_file() else None


def bound_spec_ref(
    value: ArtifactRef | str | Path,
    *,
    request: CookPreparationRequest,
) -> tuple[ArtifactRef, str]:
    if isinstance(value, ArtifactRef):
        if value.role != "spec":
            raise CookEvidenceError("bound spec must use the spec artifact role")
        raw = resolve_ref(value, request.artifact_root)
        reference = value
    else:
        path = Path(value).expanduser().resolve()
        raw = read_path(path)
        digest = digest_bytes(raw)
        expected = request.artifact_root.resolve() / (
            f"sha256-{digest.removeprefix('sha256:')}"
        )
        if path != expected:
            raise CookEvidenceError("bound spec must be a retained host artifact")
        reference = ArtifactRef(
            artifact_id=f"{request.request_id}/spec",
            role="spec",
            uri=path.as_uri(),
            digest=digest,
            size_bytes=len(raw),
            media_type="text/markdown",
            schema_uri=None,
        )
    try:
        return reference, raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise CookEvidenceError("bound spec is not UTF-8") from exc


def spec_readiness(
    source: ClassifiedCookInput,
    *,
    spec_ref: ArtifactRef,
    raw: bytes,
) -> MoldCookSpecReadiness | None:
    if source.kind not in {
        MoldCookInputKind.DIRECT_SPEC,
        MoldCookInputKind.SLUG,
    }:
        return None
    readiness = evaluate_mold_cook_spec(raw, spec_ref=spec_ref)
    identity = readiness.spec_slug
    if source.kind is MoldCookInputKind.DIRECT_SPEC and source.path is not None:
        if source.path.stem != identity:
            raise PreparationFailure(
                "spec-identity-conflict",
                f"spec path stem {source.path.stem!r} does not match frontmatter slug {identity!r}",
                path=str(source.path),
            )
    if source.kind is MoldCookInputKind.SLUG and source.source != identity:
        raise PreparationFailure(
            "spec-identity-conflict",
            f"requested slug {source.source!r} does not match frontmatter slug {identity!r}",
        )
    return readiness


def continuity_hold(
    source: ClassifiedCookInput,
    repository_root: Path,
    *,
    identity: str | None = None,
) -> CookExecutionHold | None:
    if source.kind is MoldCookInputKind.TASK and identity is None:
        return None
    if source.kind not in {
        MoldCookInputKind.DIRECT_SPEC,
        MoldCookInputKind.SLUG,
        MoldCookInputKind.TASK,
    }:
        return None
    canonical_identity = identity or (
        source.path.stem if source.path is not None else source.source
    )
    resolution: Resolution = resolve(canonical_identity, workspace_root=repository_root)
    if resolution.outcome in {
        ResolutionOutcome.NOT_FOUND,
        ResolutionOutcome.AUTHORITATIVE,
    }:
        return None
    detail = resolution.detail or (
        f"continuity resolution returned {resolution.outcome.value}"
    )
    kind = (
        CookHoldKind.INTEGRITY
        if resolution.outcome is ResolutionOutcome.ERROR
        else CookHoldKind.BLOCKED
    )
    return CookExecutionHold(
        hold_id=f"continuity-{hashlib.sha256(canonical_identity.encode()).hexdigest()[:16]}",
        kind=kind,
        reason=detail,
    )
