"""Check supplied dispatch observations against an Age review plan."""

from __future__ import annotations

from easy_cheese.shared.fanout.age_route import check_execution
from easy_cheese.shared.manifest_io import json_command

main = json_command(
    check_execution,
    "usage: review-plan-check [<request.json>]",
    keys=("plan", "observations"),
)
