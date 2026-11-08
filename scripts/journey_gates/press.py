"""Press journey gate: Press adds tests only and never edits or publishes production code."""

# gate:strip-begin
from __future__ import annotations

from journey_gates.common import (
    Workspace,
    emit,
    inside_rel,
    is_test,
    rule_publication,
    rule_tests,
    rule_unverified_ok,
    targets,
)

# gate:strip-end

CODE = (".py", ".js", ".ts", ".tsx", ".go", ".rs", ".sh", ".rb", ".java", ".c", ".cpp")

workspace = Workspace()
failures: set[str] = set()
if not workspace.has_turn:
    failures.add("no-trace")
rule_publication(workspace, failures)
rule_tests(workspace, failures)
rule_unverified_ok(workspace, failures, require_run=True)

for rel in workspace.output:
    if "__pycache__" in rel or is_test(rel) or not workspace.raw_changed(rel):
        continue
    if rel in workspace.fixtures or rel.endswith(CODE):
        failures.add("production-changed")
for rel in workspace.fixtures:
    if workspace.deleted(rel) and not is_test(rel):
        failures.add("production-changed")

for rel in workspace.fixtures:
    if not is_test(rel) and targets(workspace, rel):
        failures.add("production-write")
for _, target in workspace.write_targets():
    rel = inside_rel(workspace, target)
    if rel is not None and rel.endswith(CODE) and not is_test(rel):
        failures.add("production-write")

emit(failures)
