---
name: press
description: This skill should be used right after `/cook` produces green changes, when the user wants the test surface hardened before review or shipping — phrases like "press the changes", "harden this", "check coverage", "strengthen the tests", "are the tests good enough", "press before /age", "/press". Reads the spec + cooked diff, maps changed behavior to tests, finds weak assertions and missing boundaries, adds focused hardening tests, and produces a readiness report. Use even when the user wants to "tighten things up" before review. Do NOT use to add broad new behavior — only corrective fixes that hardening tests force.
license: MIT
---

# /press

Use this skill after `/cook` has produced green implementation changes and before review or shipping.

Do not use it to implement broad new behavior. Press may add or strengthen tests and make tiny corrective fixes only when a test exposes a clear defect in the cooked scope.

## Flow

1. **Read** — load the spec or acceptance criteria and the cooked diff.
2. **Map** — for each changed behaviour, find the test(s) that cover it via `cheez-search`.
3. **Gap analysis** — identify weak assertions, missing boundaries, and uncovered integration seams. See `references/gap-analysis.md` for what counts as a gap and the priority order.
4. **Add focused tests** — observe red first when behaviour changes. Use `cheez-write` for precise edits.
5. **Corrective fixes** — only for defects the hardening tests expose. No new behaviour.
6. **Run checks** — narrowest useful tests, then relevant wider gates already in the project.
7. **Report** — ready, follow-up, or blocked.

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
