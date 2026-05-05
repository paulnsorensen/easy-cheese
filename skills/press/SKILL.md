---
name: press
description: This skill should be used right after `/cook` produces green changes, when the user wants the test surface hardened before review or shipping — phrases like "press the changes", "harden this", "check coverage", "strengthen the tests", "are the tests good enough", "press before /age", "/press". Reads the spec + cooked diff, maps changed behavior to tests, finds weak assertions and missing boundaries, adds focused hardening tests, and produces a readiness report. Use even when the user wants to "tighten things up" before review. Do NOT use to add broad new behavior — only corrective fixes that hardening tests force.
license: MIT
---

# /press

Use this skill after `/cook` has produced green implementation changes and before review or shipping.

Do not use it to implement broad new behavior. Press may add or strengthen tests and make tiny corrective fixes only when a test exposes a clear defect in the cooked scope.

## Flow

1. Read the spec or acceptance criteria and the cooked diff.
2. Map changed behavior to existing and new tests.
3. Identify weak assertions, missing boundaries, and uncovered integration seams.
4. Add focused tests for meaningful gaps; observe red first when behavior changes.
5. Make minimal corrective fixes only for defects exposed by the hardening tests.
6. Run relevant test commands.
7. Report ready, follow-up, or blocked.

## Preferred tools and fallbacks

| Need | Prefer | Fallback |
| --- | --- | --- |
| Diff review | `delta` | plain `git diff` |
| Coverage/blast radius | code review graph, Serena or LSP | `ripgrep` callers/imports and test references |
| Precise test edits | tilth edit | harness edit tools or patch application |
| Test discovery | `sg`, ripgrep | package manager test listings or file tree |

If optional tools are missing, press a narrower surface and state the residual risk.

## Testing priority

1. Spec compliance: promised behavior has executable coverage.
2. Assertion strength: tests fail for wrong values, errors, or state.
3. Boundary behavior: empty, missing, malformed, minimal, and maximum inputs.
4. Integration seams: filesystem, subprocess, network, time, or dependency failure when in scope.
5. Happy path regression: the primary user path still passes.

## Output

```markdown
## Press Report

### Checks run
- <command>: <pass|fail|skipped with reason>

### Findings
| Severity | Category | Evidence | Recommendation |
| --- | --- | --- | --- |

### Coverage
- Spec coverage:
- Boundary coverage:
- Assertion strength:

### Handoff
<ready for /age | follow-up recommended | blocked>
```

## Rules

- Do not weaken assertions.
- Do not broaden implementation beyond the cooked contract.
- Surface medium and high findings explicitly; summarize low findings.
