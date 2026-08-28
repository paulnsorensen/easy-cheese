"""JSON CLI wrapper for the receipt-derived Press route."""

from __future__ import annotations

import sys
from dataclasses import asdict

from easy_cheese.shared.manifest_io import json_command

from .press_route import (
    Continue,
    Dispatch,
    ReceiptChainError,
    Stop,
    route_from_receipt,
)

_EXPECTED_KEYS = {
    "outcome",
    "current_receipt",
    "phase_token_ref",
    "phase_token_sha256",
}


def _action_payload(action: Continue | Dispatch | Stop) -> dict[str, object]:
    if isinstance(action, Continue):
        name = "continue"
    elif isinstance(action, Dispatch):
        name = "dispatch"
    else:
        name = "stop"
    return {"action": name, **asdict(action)}


def _route(**payload: object) -> dict[str, object]:
    if set(payload) != _EXPECTED_KEYS:
        raise ValueError(
            "request must contain exactly outcome, current_receipt, "
            "phase_token_ref, and phase_token_sha256"
        )
    try:
        action = route_from_receipt(
            payload["outcome"],
            payload["current_receipt"],
            payload["phase_token_ref"],
            payload["phase_token_sha256"],
        )
    except ReceiptChainError as exc:
        raise ValueError(str(exc)) from exc
    return _action_payload(action)


main = json_command(_route, "usage: press_route_cli.py [<request.json>]")


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
