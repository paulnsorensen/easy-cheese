"""Filesystem orchestration for the evidence-gated distillation lifecycle."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import math
import os
import shutil
import tempfile
from collections.abc import Callable
from dataclasses import fields, is_dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path, PurePosixPath
from types import ModuleType, SimpleNamespace
from typing import Any, Mapping, Sequence

import yaml

from .adjudication import (
    export_llm_pairs,
    freeze_human_labels,
    reconcile,
    record_llm_labels,
)
from .canonical import validate_family
from .contracts import (
    CanonicalCenter,
    DependencyInventoryV1,
    DistillationFamily,
    DistillationRun,
    FusionProfile,
    HumanDispositionV1,
    LoadEvent,
    ModelLock,
    ProposalV1,
    RelationKind,
    RunState,
    TokenMetricProfile,
)
from .interaction import InteractionResult, gate_interactions
from .representations import RepresentationCandidate, choose_representation
from .retrieval import LocalScoringRunner, ScoringPair
from .tokens import loaded_tokens, token_savings
from .transaction import apply_family


class LifecycleError(ValueError):
    """A lifecycle artifact or command violates the locked protocol."""


def require_context_path(path: Path) -> Path:
    """Return a normalized evidence path only when it lives under `.context`."""
    resolved = path.expanduser().resolve()
    if ".context" not in resolved.parts:
        raise LifecycleError(f"generated evidence must be written under .context: {path}")
    return resolved


def require_new_run_path(path: Path) -> Path:
    """Return a normalized run path only when no record exists there."""
    target = require_context_path(path)
    if target.exists():
        raise LifecycleError(f"run already exists: {path}")
    return target


def _plain(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value):
        return {field.name: _plain(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, Mapping):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, tuple | list):
        return [_plain(item) for item in value]
    return value


def load_document(path: Path) -> Any:
    text = path.read_text(encoding="utf-8")
    value = yaml.safe_load(text) if path.suffix in {".yaml", ".yml"} else json.loads(text)
    if value is None:
        raise LifecycleError(f"empty lifecycle document: {path}")
    return value


def _encoded(path: Path, value: Any) -> bytes:
    plain = _plain(value)
    if path.suffix in {".yaml", ".yml"}:
        return yaml.safe_dump(plain, sort_keys=True, allow_unicode=True).encode()
    return (json.dumps(plain, sort_keys=True, indent=2) + "\n").encode()


def write_evidence(path: Path, value: Any) -> Path:
    target = require_context_path(path)
    apply_family("lifecycle-evidence", {target: _encoded(target, value)})
    return target


def _run(value: Mapping[str, Any]) -> DistillationRun:
    return DistillationRun(
        run_id=str(value["run_id"]),
        state=RunState(value["state"]),
        human_labels_digest=value.get("human_labels_digest"),
        llm_labels_digest=value.get("llm_labels_digest"),
        human_labels_frozen_at=value.get("human_labels_frozen_at"),
    )


def initialize_run(path: Path, run_id: str) -> DistillationRun:
    target = require_new_run_path(path)
    run = DistillationRun(run_id, RunState.PREPARED)
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        with target.open("xb") as stream:
            stream.write(_encoded(target, run))
            stream.flush()
            os.fsync(stream.fileno())
    except FileExistsError as error:
        raise LifecycleError(f"run already exists: {path}") from error
    except BaseException:
        target.unlink(missing_ok=True)
        raise
    return run


def freeze_labels(run_path: Path, labels_path: Path, frozen_at: str) -> DistillationRun:
    run_path = require_context_path(run_path)
    run = freeze_human_labels(_run(load_document(run_path)), load_document(labels_path), frozen_at=frozen_at)
    write_evidence(run_path, run)
    return run


def _source_pair(value: Mapping[str, Any]) -> SimpleNamespace:
    def side(item: Mapping[str, Any]) -> dict[str, Any]:
        span = item.get("source_span", item.get("span"))
        if not isinstance(span, Mapping):
            raise LifecycleError("dataset pair side is missing a source span")
        return {"source_span": {"path": item["path"], "start": span["start"], "end": span["end"]}}

    return SimpleNamespace(pair_id=value["pair_id"], left=side(value["left"]), right=side(value["right"]))


def export_pairs(run_path: Path, dataset_path: Path, output_path: Path) -> tuple[Any, ...]:
    dataset_path = require_context_path(dataset_path)
    run = _run(load_document(require_context_path(run_path)))
    dataset = load_document(dataset_path)
    pairs = export_llm_pairs(run, tuple(_source_pair(pair) for pair in dataset["pairs"]))
    write_evidence(output_path, pairs)
    return pairs


def record_labels(run_path: Path, labels_path: Path) -> DistillationRun:
    labels_path = require_context_path(labels_path)
    run_path = require_context_path(run_path)
    run = record_llm_labels(_run(load_document(run_path)), load_document(labels_path))
    write_evidence(run_path, run)
    return run


def reconcile_labels(
    run_path: Path,
    human_path: Path,
    llm_path: Path,
    adjudications_path: Path,
    output_path: Path,
) -> tuple[Any, ...]:
    run_path = require_context_path(run_path)
    llm_path = require_context_path(llm_path)
    result = reconcile(
        _run(load_document(run_path)),
        load_document(human_path),
        load_document(llm_path),
        load_document(adjudications_path),
    )
    output_path = require_context_path(output_path)
    apply_family(
        f"reconcile-{result.run.run_id}",
        {run_path: _encoded(run_path, result.run), output_path: _encoded(output_path, result.annotations)},
    )
    return result.annotations


def validate_annotations(values: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    if not values:
        raise LifecycleError("annotations cannot be empty")
    pair_ids = [str(value["pair_id"]) for value in values]
    if len(pair_ids) != len(set(pair_ids)):
        raise LifecycleError("annotations must contain unique pair IDs")
    eligible = []
    for value in values:
        reconciliation = value.get("reconciliation", {})
        relation = RelationKind(reconciliation.get("resolved_relation", value["human_relation"]))
        complete = value.get("status") == "reconciled" and reconciliation.get("complete") is True
        rewrite_eligible = reconciliation.get("rewrite_eligible") is True
        expected = complete and relation in {RelationKind.EQUIVALENT, RelationKind.SHARED_SHELL}
        if rewrite_eligible != expected:
            raise LifecycleError(f"annotation eligibility is inconsistent: {value['pair_id']}")
        if expected:
            eligible.append(value["pair_id"])
    return {"annotation_count": len(values), "eligible_pair_ids": sorted(eligible), "valid": True}


_SCORE_FIELDS = (
    "arctic_s",
    "dense",
    "sparse",
    "colbert",
    "fused",
    "left_entails_right",
    "right_entails_left",
    "left_contradicts_right",
    "right_contradicts_left",
)


def validate_score_coverage(
    annotations: Sequence[Mapping[str, Any]], scores: Sequence[Mapping[str, Any]]
) -> None:
    annotation_ids = {value["pair_id"] for value in annotations}
    score_ids = [value["pair_id"] for value in scores]
    if len(score_ids) != len(set(score_ids)) or set(score_ids) != annotation_ids:
        raise LifecycleError("scores must cover every annotated pair exactly once")
    profiles = {
        (value["model_profile_digest"], value["fusion_profile_digest"])
        for value in scores
    }
    if len(profiles) != 1:
        raise LifecycleError("scores must share one model and fusion profile")
    for value in scores:
        if any(
            isinstance(value.get(name), bool)
            or not isinstance(value.get(name), int | float)
            or not math.isfinite(value[name])
            for name in _SCORE_FIELDS
        ):
            raise LifecycleError(f"score evidence is incomplete: {value['pair_id']}")


def _contract(model: type, value: Mapping[str, Any]):
    names = model.__dataclass_fields__  # type: ignore[attr-defined]
    return model(**{name: value[name] for name in names if name in value and name != "schema_version"})


def _load_adapter_module(path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location("skill_distill_local_adapters", path)
    if spec is None or spec.loader is None:
        raise LifecycleError(f"cannot load local adapter module: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if not all(hasattr(module, name) for name in ("arctic", "bge", "nli")):
        raise LifecycleError("adapter module must expose arctic, bge, and nli adapters")
    return module


def score_dataset(
    dataset_path: Path,
    output_path: Path,
    adapter_module: Path,
    locks_path: Path,
    snapshots: Mapping[str, Path],
    fusion_path: Path,
    inventory_path: Path,
) -> tuple[Any, ...]:
    output_path = require_context_path(output_path)
    dataset_path = require_context_path(dataset_path)
    dataset = load_document(dataset_path)
    pairs = tuple(
        ScoringPair(pair["pair_id"], pair["left"]["original_excerpt"], pair["right"]["original_excerpt"])
        for pair in dataset["pairs"]
    )
    locks = load_document(locks_path)
    by_id = {value["model_id"]: _contract(ModelLock, value) for value in locks}
    from .retrieval import ARCTIC_S_MODEL, BGE_M3_MODEL, NLI_MODEL

    module = _load_adapter_module(adapter_module)
    scores = LocalScoringRunner(module.arctic, module.bge, module.nli).score(
        pairs,
        by_id[ARCTIC_S_MODEL], snapshots["arctic"],
        by_id[BGE_M3_MODEL], snapshots["bge"],
        by_id[NLI_MODEL], snapshots["nli"],
        _contract(FusionProfile, load_document(fusion_path)),
        _contract(DependencyInventoryV1, load_document(inventory_path)),
    )
    score_values = _plain(scores)
    validate_score_coverage(
        ({"pair_id": pair.pair_id} for pair in pairs),
        score_values,
    )
    write_evidence(output_path, score_values)
    return scores


_SHA256 = frozenset("0123456789abcdef")
_VARIANT_NAMES = ("physical-reference", "compact-inline")


def _sha256(value: Any, field: str) -> str:
    if not isinstance(value, str) or len(value) != 64 or set(value) - _SHA256:
        raise LifecycleError(f"{field} must be a lowercase SHA-256 digest")
    return value


def _canonical_load_path(value: Any) -> str:
    if not isinstance(value, str) or not value:
        raise LifecycleError("load event canonical_path is required")
    path = PurePosixPath(value)
    if path.is_absolute() or path.as_posix() != value or any(part in {".", ".."} for part in path.parts):
        raise LifecycleError(f"load event path is not canonical: {value}")
    return value


def _token_profile(value: Any) -> TokenMetricProfile:
    if not isinstance(value, Mapping) or value.get("schema_version") != "token-metric-profile-v1":
        raise LifecycleError("token metric profile is missing or has the wrong schema version")
    identity = _sha256(value.get("tokenizer_identity_digest"), "tokenizer identity")
    raw_events = value.get("load_events")
    if not isinstance(raw_events, list) or not raw_events:
        raise LifecycleError("token metric profile requires nonempty load events")
    events = []
    for raw in raw_events:
        if not isinstance(raw, Mapping) or raw.get("schema_version") != "load-event-v1":
            raise LifecycleError("load event is incomplete or has the wrong schema version")
        token_count = raw.get("token_count")
        if isinstance(token_count, bool) or not isinstance(token_count, int) or token_count < 0:
            raise LifecycleError("load event token_count must be a non-negative integer")
        event_identity = _sha256(raw.get("tokenizer_identity_digest"), "load event tokenizer identity")
        if event_identity != identity:
            raise LifecycleError("load event tokenizer identity drift")
        role = raw.get("role")
        if not isinstance(role, str) or not role:
            raise LifecycleError("load event role is required")
        events.append(LoadEvent(
            role,
            _canonical_load_path(raw.get("canonical_path")),
            _sha256(raw.get("content_digest"), "load event content"),
            event_identity,
            token_count,
        ))
    return TokenMetricProfile(identity, tuple(events))


def _profile_paths(profile: TokenMetricProfile) -> set[str]:
    return {event.canonical_path for event in profile.load_events}


def _validate_profile_content(
    profile: TokenMetricProfile,
    expected: Mapping[str, bytes],
    label: str,
) -> None:
    missing = _profile_paths(profile) - set(expected)
    if missing:
        raise LifecycleError(f"{label} token profile paths are absent from its applied-tree view")
    for event in profile.load_events:
        digest = hashlib.sha256(expected[event.canonical_path]).hexdigest()
        if event.content_digest != digest:
            raise LifecycleError(f"{label} token profile content digest does not match exact bytes")


def _validate_changed_content(
    profile: TokenMetricProfile,
    changes: Mapping[str, bytes],
    label: str,
) -> None:
    if not set(changes) <= _profile_paths(profile):
        raise LifecycleError(f"{label} token profile does not represent every proposal change")
    for event in profile.load_events:
        if event.canonical_path in changes:
            digest = hashlib.sha256(changes[event.canonical_path]).hexdigest()
            if event.content_digest != digest:
                raise LifecycleError(f"{label} token profile content digest does not match exact bytes")


def _proposal_profiles(draft: Mapping[str, Any]) -> tuple[TokenMetricProfile, dict[str, TokenMetricProfile]]:
    if "original_loaded_tokens" in draft:
        raise LifecycleError("free token totals are forbidden; provide measured token profiles")
    original = _token_profile(draft.get("original_token_profile"))
    variants = draft.get("variants")
    if not isinstance(variants, Mapping) or set(variants) != set(_VARIANT_NAMES):
        raise LifecycleError("proposal requires physical-reference and compact-inline variants")
    profiles = {}
    for name in _VARIANT_NAMES:
        variant = variants[name]
        if not isinstance(variant, Mapping):
            raise LifecycleError(f"{name} variant must be an object")
        if not isinstance(variant.get("behavior_passed"), bool):
            raise LifecycleError(f"{name} variant requires boolean behavior evidence")
        if "loaded_tokens" in variant:
            raise LifecycleError("free token totals are forbidden; provide measured token profiles")
        profiles[name] = _token_profile(variant.get("token_metric_profile"))
        changes = variant.get("changes")
        if not isinstance(changes, Mapping) or not changes or any(
            not isinstance(path, str) or not isinstance(content, str)
            for path, content in changes.items()
        ):
            raise LifecycleError(f"{name} variant requires text changes")
        encoded_changes = {
            _canonical_load_path(path): content.encode() for path, content in changes.items()
        }
        _validate_changed_content(profiles[name], encoded_changes, name)
    if any(profile.tokenizer_identity_digest != original.tokenizer_identity_digest for profile in profiles.values()):
        raise LifecycleError("proposal token profiles use different tokenizer identities")
    return original, profiles


def _require_human_approval(proposal_path: Path, disposition_path: Path | None) -> None:
    if disposition_path is None:
        raise LifecycleError("concern or abstain requires a separate human disposition record")
    path = require_context_path(disposition_path)
    value = load_document(path)
    expected_fields = {
        "proposal_digest", "decision", "reviewer_identity", "reviewed_at", "commitment", "schema_version"
    }
    if (
        not isinstance(value, Mapping)
        or set(value) != expected_fields
        or value.get("schema_version") != "human-disposition-v1"
    ):
        raise LifecycleError("human disposition is incomplete or has the wrong schema version")
    text_fields = ("decision", "reviewer_identity", "reviewed_at", "commitment")
    if any(not isinstance(value[field], str) or not value[field] for field in text_fields):
        raise LifecycleError("human disposition fields must be nonempty strings")
    record = HumanDispositionV1(
        proposal_digest=_sha256(value["proposal_digest"], "proposal digest"),
        decision=value["decision"],
        reviewer_identity=value["reviewer_identity"],
        reviewed_at=value["reviewed_at"],
        commitment=value["commitment"],
    )
    if record.proposal_digest != hashlib.sha256(proposal_path.read_bytes()).hexdigest():
        raise LifecycleError("human disposition proposal digest does not match proposal bytes")
    if record.decision != "approve":
        raise LifecycleError("human disposition decision must explicitly approve")
    if not record.reviewer_identity or not record.commitment:
        raise LifecycleError("human disposition requires reviewer identity and commitment")
    try:
        reviewed_at = datetime.fromisoformat(record.reviewed_at.replace("Z", "+00:00"))
    except ValueError as error:
        raise LifecycleError("human disposition reviewed_at must be an ISO-8601 timestamp") from error
    if reviewed_at.tzinfo is None:
        raise LifecycleError("human disposition reviewed_at must include a timezone")


def _diagnostic_passed(
    evidence: Mapping[str, Any], proposal_path: Path, disposition_path: Path | None
) -> bool:
    disposition = evidence.get("llm_disposition")
    if disposition == "pass":
        return True
    if disposition not in {"concern", "abstain"}:
        return False
    _require_human_approval(proposal_path, disposition_path)
    return True


def build_proposals(
    annotations_path: Path,
    scores_path: Path,
    drafts_path: Path,
    output_dir: Path,
) -> tuple[Path, ...]:
    annotations_path = require_context_path(annotations_path)
    scores_path = require_context_path(scores_path)
    drafts_path = require_context_path(drafts_path)
    annotations = load_document(annotations_path)
    validate_score_coverage(annotations, load_document(scores_path))
    eligible = set(validate_annotations(annotations)["eligible_pair_ids"])
    drafts = load_document(drafts_path)
    output_dir = require_context_path(output_dir)
    written = []
    for draft in drafts:
        pair_ids = set(draft["pair_ids"])
        if not pair_ids or not pair_ids <= eligible:
            raise LifecycleError("proposal includes an incomplete or rewrite-ineligible pair")
        center_value = draft["canonical_center"]
        center = CanonicalCenter(
            center_value["family_id"], tuple(center_value["clauses"]), center_value["member_residuals"]
        )
        family = DistillationFamily(
            draft["family_id"], RelationKind(draft["relation"]), tuple(draft["members"]), center
        )
        validate_family(family, draft["original_obligations"])
        original_profile, profiles = _proposal_profiles(draft)
        candidates = tuple(
            RepresentationCandidate(name, loaded_tokens(profiles[name]), value["behavior_passed"])
            for name, value in draft["variants"].items()
        )
        choice = choose_representation(loaded_tokens(original_profile), candidates)
        chosen_profile = profiles[choice.name]
        proposal = ProposalV1(
            family.family_id,
            center,
            center.member_residuals,
            original_profile,
            draft["variants"]["physical-reference"],
            draft["variants"]["compact-inline"],
            token_savings(original_profile, chosen_profile),
            {**draft["behavioral_evidence"], "selected_representation": choice.name},
            draft["reversal_patch"],
        )
        path = output_dir / f"{proposal.family_id}.json"
        write_evidence(path, proposal)
        written.append(path)
    return tuple(written)


def _repository_path(root: Path, relative: str) -> Path:
    path = (root / relative).resolve()
    if root not in path.parents:
        raise LifecycleError("proposal path escapes the repository")
    return path


def _has_symlink_component(root: Path, relative: str) -> bool:
    path = root
    for part in Path(relative).parts:
        path /= part
        if path.is_symlink():
            return True
    return False


def _neutralize_escaping_symlinks(mirror: Path) -> None:
    """Remove any symlink in the mirror whose resolved target leaves the mirror.

    ``shutil.copytree(..., symlinks=True)`` copies symlinks verbatim instead of
    following them, which stops unbounded recursion through a directory symlink
    that points back at an ancestor. But a symlink copied verbatim still points
    at its original target - if that target is absolute, or escapes the mirror
    via enough ``..`` segments, a gate writing through the symlink would mutate
    the real filesystem instead of the disposable mirror. Stripping any symlink
    whose resolved target lands outside the mirror closes that gap while
    leaving symlinks that stay within the mirror untouched.
    """
    root = mirror.resolve()
    for dirpath, dirnames, filenames in os.walk(mirror, followlinks=False):
        current = Path(dirpath)
        for name in (*dirnames, *filenames):
            candidate = current / name
            if not candidate.is_symlink():
                continue
            target = candidate.resolve()
            if target != root and root not in target.parents:
                candidate.unlink()


def _representation_view(
    root: Path,
    profile: TokenMetricProfile,
    changes: Mapping[str, bytes],
    label: str,
) -> dict[str, bytes]:
    view = dict(changes)
    for relative in _profile_paths(profile) - set(changes):
        path = _repository_path(root, relative)
        if not path.is_file():
            raise LifecycleError(f"{label} token profile requires an existing loaded file: {relative}")
        view[relative] = path.read_bytes()
    return view


def _validate_proposal_views(
    root: Path,
    original: TokenMetricProfile,
    profiles: Mapping[str, TokenMetricProfile],
    variant_changes: Mapping[str, Mapping[str, bytes]],
) -> None:
    _validate_profile_content(
        original, _representation_view(root, original, {}, "original"), "original"
    )
    for name, profile in profiles.items():
        _validate_profile_content(
            profile,
            _representation_view(root, profile, variant_changes[name], name),
            name,
        )


def apply_proposal(
    proposal_path: Path,
    repository: Path,
    post_write_gate: Callable[[Path], bool],
    disposition_path: Path | None = None,
) -> tuple[Path, ...]:
    proposal_path = require_context_path(proposal_path)
    value = load_document(proposal_path)
    evidence = value["behavioral_evidence"]
    deterministic = all(
        evidence.get(name) is True
        for name in ("deterministic_passed", "behavior_passed", "overlap_passed")
    )
    if not deterministic or not _diagnostic_passed(evidence, proposal_path, disposition_path):
        raise LifecycleError("proposal has not passed every deterministic and diagnostic gate")
    selected_name = evidence.get("selected_representation")
    if not isinstance(selected_name, str) or not selected_name:
        raise LifecycleError("proposal evidence is missing selected_representation")
    proposal_profiles = _proposal_profiles({
        "original_token_profile": value["original_token_profile"],
        "variants": {
            name: value[name.replace("-", "_") + "_variant"] for name in _VARIANT_NAMES
        },
    })
    variant_changes = {
        name: {
            relative: content.encode()
            for relative, content in value[name.replace("-", "_") + "_variant"]["changes"].items()
        }
        for name in _VARIANT_NAMES
    }
    relative_changes = variant_changes[selected_name]
    root = repository.resolve()
    resolved_changes = tuple(
        ((root / relative).resolve(), relative, content)
        for relative, content in relative_changes.items()
    )
    targets = tuple(path for path, _relative, _content in resolved_changes)
    if len(set(targets)) != len(targets):
        raise LifecycleError("proposal changes contain duplicate resolved targets")
    if any(
        _has_symlink_component(root, relative)
        for _path, relative, _content in resolved_changes
    ):
        raise LifecycleError("proposal change path contains a symlink")
    if any(root not in path.parents for path in targets):
        raise LifecycleError("proposal path escapes the repository")
    changes = {path: content for path, _relative, content in resolved_changes}
    if any(path.exists() and not path.is_file() for path in changes):
        raise LifecycleError("proposal change target exists but is not a file")

    original, profiles = proposal_profiles
    _validate_proposal_views(root, original, profiles, variant_changes)
    snapshots = {path: path.read_bytes() if path.exists() else None for path in changes}

    with tempfile.TemporaryDirectory(prefix="skill-distill-apply-") as temporary:
        mirror = Path(temporary) / "repository"
        shutil.copytree(
            root,
            mirror,
            symlinks=True,
            ignore=shutil.ignore_patterns(".git", ".venv", "node_modules", "__pycache__"),
        )
        _neutralize_escaping_symlinks(mirror)
        mirror_changes = {mirror / path.relative_to(root): content for path, content in changes.items()}
        apply_family(value["family_id"], mirror_changes)
        if not post_write_gate(mirror):
            raise RuntimeError(f"family gate failed: {value['family_id']}")

    refreshed = {path: path.read_bytes() if path.exists() else None for path in changes}
    if refreshed != snapshots:
        raise LifecycleError("proposal change targets changed while the applied-tree gate ran")
    _validate_proposal_views(root, original, profiles, variant_changes)
    return apply_family(value["family_id"], changes).applied_paths


def verify_run(run_path: Path, evidence_path: Path) -> InteractionResult:
    evidence_path = require_context_path(evidence_path)
    run = _run(load_document(require_context_path(run_path)))
    if run.state is not RunState.RECONCILED:
        raise LifecycleError("verify requires a reconciled run")
    evidence = load_document(evidence_path)
    retained = tuple(evidence.get("retained_families", ()))
    if len(retained) != len(set(retained)):
        raise LifecycleError("interaction evidence repeats a family")
    failing_subsets = {
        tuple(sorted(subset)) for subset in evidence.get("failing_subsets", ())
    }
    if any(set(subset) - set(retained) for subset in failing_subsets):
        raise LifecycleError("interaction evidence names invalid families")
    result = gate_interactions(
        retained,
        lambda subset: tuple(sorted(subset)) not in failing_subsets,
    )
    if not result.passed:
        raise LifecycleError(f"final interaction gate failed: {', '.join(result.failing_families)}")
    return result
