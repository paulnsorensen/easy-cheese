"""Command-line boundary for the deterministic distillation lifecycle."""

from __future__ import annotations

import argparse
import json
import subprocess
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path

from . import lifecycle
from .contracts import ApplyGateV1


def _prepare(args: argparse.Namespace) -> int:
    from .prepare import prepare_to_path

    lifecycle.require_context_path(args.out)
    if args.run:
        lifecycle.require_new_run_path(args.run)
    prepare_to_path(args.report, args.adversarial_controls, args.out)
    if args.run:
        lifecycle.initialize_run(args.run, args.run_id)
    return 0


def _freeze(args: argparse.Namespace) -> int:
    lifecycle.freeze_labels(args.run, args.labels, args.frozen_at)
    return 0


def _export(args: argparse.Namespace) -> int:
    lifecycle.export_pairs(args.run, args.dataset, args.out)
    return 0


def _record(args: argparse.Namespace) -> int:
    lifecycle.record_labels(args.run, args.labels)
    return 0


def _reconcile(args: argparse.Namespace) -> int:
    lifecycle.reconcile_labels(args.run, args.human, args.llm, args.adjudications, args.out)
    return 0


def _score(args: argparse.Namespace) -> int:
    lifecycle.score_dataset(
        args.dataset,
        args.out,
        args.adapters,
        args.locks,
        {"arctic": args.arctic_snapshot, "bge": args.bge_snapshot, "nli": args.nli_snapshot},
        args.fusion_profile,
        args.dependency_inventory,
    )
    return 0


def _validate(args: argparse.Namespace) -> int:
    report = lifecycle.validate_annotations(lifecycle.load_document(args.annotations))
    if args.out:
        lifecycle.write_evidence(args.out, report)
    else:
        print(json.dumps(report, sort_keys=True))
    return 0


def _propose(args: argparse.Namespace) -> int:
    lifecycle.build_proposals(args.annotations, args.scores, args.drafts, args.out)
    return 0


_APPLY_GATES = ("deterministic", "behavior", "overlap")


def _resolve_apply_gate(contract_path: Path) -> Callable[[Path], bool]:
    raw = lifecycle.load_document(lifecycle.require_context_path(contract_path))
    if not isinstance(raw, Mapping) or raw.get("schema_version") != "apply-gate-v1":
        raise lifecycle.LifecycleError("apply gate contract has the wrong schema version")

    def command(name: str) -> tuple[str, ...]:
        value = raw.get(name)
        if (
            not isinstance(value, list)
            or not value
            or any(not isinstance(part, str) or not part for part in value)
        ):
            raise lifecycle.LifecycleError(f"apply gate contract requires a {name} command")
        return tuple(value)

    contract = ApplyGateV1(*(command(name) for name in _APPLY_GATES))

    def gate(repository: Path) -> bool:
        failures = []
        for name in _APPLY_GATES:
            try:
                result = subprocess.run(getattr(contract, name), cwd=repository, check=False)
            except OSError as error:
                failures.append(f"{name} (gate command not found in mirror: {error})")
                continue
            if result.returncode != 0:
                failures.append(f"{name} (exit {result.returncode})")
        gate.failures = tuple(failures)
        return not failures

    return gate


def _apply(args: argparse.Namespace) -> int:
    gate = _resolve_apply_gate(args.gate_contract)
    try:
        lifecycle.apply_proposal(args.proposal, args.repository, gate, args.disposition)
    except RuntimeError as error:
        failures = getattr(gate, "failures", None)
        if failures:
            raise RuntimeError(f"{error}: {', '.join(failures)}") from error
        raise
    return 0


def _verify(args: argparse.Namespace) -> int:
    lifecycle.verify_run(args.run, args.evidence)
    return 0


def _path_argument(parser: argparse.ArgumentParser, name: str, **kwargs: object) -> None:
    parser.add_argument(name, type=Path, **kwargs)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="skill-distill")
    commands = parser.add_subparsers(dest="command", required=True)

    prepare = commands.add_parser("prepare", help="build the deterministic pilot dataset")
    _path_argument(prepare, "--report", required=True)
    _path_argument(prepare, "--adversarial-controls", required=True)
    _path_argument(prepare, "--out", required=True)
    _path_argument(prepare, "--run")
    prepare.add_argument("--run-id", default="skill-distill-pilot")
    prepare.set_defaults(run_command=_prepare)

    freeze = commands.add_parser("freeze-human-labels")
    _path_argument(freeze, "--run", required=True)
    _path_argument(freeze, "--labels", required=True)
    freeze.add_argument("--frozen-at", required=True)
    freeze.set_defaults(run_command=_freeze)

    export = commands.add_parser("export-llm-pairs")
    _path_argument(export, "--run", required=True)
    _path_argument(export, "--dataset", required=True)
    _path_argument(export, "--out", required=True)
    export.set_defaults(run_command=_export)

    record = commands.add_parser("record-llm-labels")
    _path_argument(record, "--run", required=True)
    _path_argument(record, "--labels", required=True)
    record.set_defaults(run_command=_record)

    reconciler = commands.add_parser("reconcile")
    for name in ("--run", "--human", "--llm", "--adjudications", "--out"):
        _path_argument(reconciler, name, required=True)
    reconciler.set_defaults(run_command=_reconcile)

    score = commands.add_parser("score")
    for name in (
        "--dataset", "--out", "--adapters", "--locks", "--arctic-snapshot",
        "--bge-snapshot", "--nli-snapshot", "--fusion-profile", "--dependency-inventory",
    ):
        _path_argument(score, name, required=True)
    score.set_defaults(run_command=_score)

    validate = commands.add_parser("validate")
    _path_argument(validate, "--annotations", required=True)
    _path_argument(validate, "--out")
    validate.set_defaults(run_command=_validate)

    propose = commands.add_parser("propose")
    _path_argument(propose, "--annotations", required=True)
    _path_argument(propose, "--scores", required=True)
    _path_argument(propose, "--drafts", required=True)
    _path_argument(propose, "--out", required=True)
    propose.set_defaults(run_command=_propose)

    apply = commands.add_parser("apply")
    _path_argument(apply, "--proposal", required=True)
    _path_argument(apply, "--repository", default=Path.cwd())
    _path_argument(apply, "--gate-contract", required=True)
    _path_argument(apply, "--disposition")
    apply.set_defaults(run_command=_apply)

    verify = commands.add_parser("verify")
    _path_argument(verify, "--run", required=True)
    _path_argument(verify, "--evidence", required=True)
    verify.set_defaults(run_command=_verify)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    try:
        return args.run_command(args)
    except (KeyError, TypeError, ValueError) as error:
        parser.error(str(error))