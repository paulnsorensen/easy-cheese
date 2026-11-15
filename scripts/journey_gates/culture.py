"""Culture journey gate: Culture writes knowledge records only; no code, no spec, no publication."""

# gate:strip-begin
from __future__ import annotations

import posixpath
import re

from journey_gates.common import (
    Workspace,
    emit,
    read_text,
    rule_publication,
)

# gate:strip-end

CODE = re.compile(r"\.(py|js|jsx|ts|tsx|go|rs|java|rb|c|h|cpp|sh|kt|swift|php)$")
SPEC_PATH = re.compile(r"(?:^|/)specs/[\w.-]+\.md$")
SPEC_FRONTMATTER = re.compile(r"^source:\s*(?:mold|agent-mini-spec)\b", re.MULTILINE)
SPEC_COMMAND = re.compile(r"\bartifact-path\s+specs\b|\bmold\.pyz\s+(?:validate-spec|finalize)\b")
SCRATCH = ("/dev/", "/tmp/", "tmp/", "$TMPDIR", "${TMPDIR")

workspace = Workspace()


def local(path: str) -> str:
    """Strip quotes and the trace's workspace root, so `/ws/tmp/x` reads as `tmp/x`."""
    path = posixpath.normpath(path.strip().strip("\"'"))
    root = workspace.root.rstrip("/")
    return path[len(root) + 1 :] if root and path.startswith(root + "/") else path


def exempt(target: str) -> bool:
    """Hidden state (`.cheese/`), scratch space, and device sinks are not workspace writes."""
    target = local(target)
    if not target or target.startswith(SCRATCH):
        return True
    return any(part.startswith(".") and part not in (".", "..") for part in target.split("/"))


def source(path: str) -> bool:
    return bool(CODE.search(path)) and not exempt(path)


failures: set[str] = set()
if not workspace.has_turn:
    failures.add("no-trace")
rule_publication(workspace, failures, commit=True)

# 1. Culture writes no source file, by tool or by shell. Hidden state and
# scratch paths stay exempt, as in the Cheese and Briesearch gates. The spec
# checks below keep no exemption.
for kind, value in workspace.steps:
    if kind == "write" and source(value):
        failures.add("write-tool-source-file")
for facts in workspace.facts.values():
    if any(source(target) for target in facts.writes):
        failures.add("bash-writes-source-file")
for rel, path in workspace.output.items():
    if not source(rel):
        continue
    if rel not in workspace.fixtures:
        failures.add("new-source-file")
    elif read_text(workspace.fixtures[rel]) != read_text(path):
        failures.add("fixture-source-changed")
for rel in workspace.fixtures:
    if source(rel) and workspace.deleted(rel):
        failures.add("fixture-source-changed")

# 2. Culture writes no spec: no specs/ path, no spec frontmatter, no Mold spec command.
for kind, value in workspace.steps:
    if kind == "write" and SPEC_PATH.search(value):
        failures.add("spec-written-by-tool")
    if kind == "shell" and SPEC_COMMAND.search(value):
        failures.add("spec-written-by-bash")
for facts in workspace.facts.values():
    if any(SPEC_PATH.search(target) for target in facts.writes):
        failures.add("spec-written-by-bash")
for rel, path in workspace.output.items():
    if rel.endswith(".md") and rel not in workspace.fixtures:
        head = read_text(path)[:600]
        if head.startswith("---") and SPEC_FRONTMATTER.search(head):
            failures.add("spec-written")

emit(failures)
