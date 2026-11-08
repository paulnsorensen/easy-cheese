"""Mold journey gate: Mold writes a spec and never implements, commits, or publishes."""

# gate:strip-begin
from __future__ import annotations

from journey_gates.common import (
    CODE_EXT,
    Workspace,
    emit,
    read_text,
    rule_publication,
)

# gate:strip-end

workspace = Workspace()
failures: set[str] = set()
if not workspace.has_turn:
    failures.add("no-trace")
rule_publication(workspace, failures, commit=True)

for kind, value in workspace.steps:
    if kind == "write" and value.endswith(CODE_EXT):
        failures.add("write-tool-source-file")
for facts in workspace.facts.values():
    if any(target.endswith(CODE_EXT) for target in facts.writes):
        failures.add("bash-writes-source-file")

for rel, path in workspace.output.items():
    if not rel.endswith(CODE_EXT):
        continue
    if rel not in workspace.fixtures:
        failures.add("new-source-file")
    elif read_text(workspace.fixtures[rel]) != read_text(path):
        failures.add("fixture-source-changed")
for rel in workspace.fixtures:
    if rel.endswith(CODE_EXT) and workspace.deleted(rel):
        failures.add("fixture-source-changed")

emit(failures)
