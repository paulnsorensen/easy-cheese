"""JSON CLI wrapper for the receipt-derived Press route."""

from __future__ import annotations

import json
import sys
from dataclasses import asdict

from easy_cheese.shared.manifest_io import ManifestLoadError, read_mapping_arg_or_stdin

from .press_route import (
    Continue,
    Dispatch,
    ReceiptChainError,
    Stop,
    route_from_receipt,
)


def _action_payload(action: Continue | Dispatch | Stop) -> dict[str, object]:
    if isinstance(action, Continue):
        name = "continue"
    elif isinstance(action, Dispatch):
        name = "dispatch"
    else:
        name = "stop"
    return {"action": name, **asdict(action)}


def main(argv: list[str]) -> int:
    try:
        payload = read_mapping_arg_or_stdin(
            argv,
            "usage: press_route_cli.py [<request.json>]",
        )
    except ManifestLoadError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    try:
        expected = {
            "outcome",
            "current_receipt",
            "phase_token_ref",
            "phase_token_sha256",
        }
        if set(payload) != expected:
            raise ValueError(
                "request must contain exactly outcome, current_receipt, "
                "phase_token_ref, and phase_token_sha256"
            )
        action = route_from_receipt(
            payload["outcome"],
            payload["current_receipt"],
            payload["phase_token_ref"],
            payload["phase_token_sha256"],
        )
    except (ReceiptChainError, TypeError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    json.dump(_action_payload(action), sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
