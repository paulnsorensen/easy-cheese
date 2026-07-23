# ADR — baseline-quality-gate-003

### ADR-003: Helper computes the classification  [status: accepted]

- **Context:** "Identical to baseline" decided by agent judgment makes the pipeline's central gate unfalsifiable and untestable; #298's acceptance criteria demand tests in both directions.
- **Decision:** `src/fanout/baseline.py::classify(baseline, current) -> {identical,new,changed,resolved}` — pure, unit-tested, bundled into the ultracook .pyz like its siblings. Signature = first line of the failure message, whitespace-normalized.
- **Alternatives:** Prose-judgment only (rejected: Rule 2 — don't eyeball what code can compute; tests could only pin wording).
- **Consequences:** The matching rule is one tunable function; exotic failure output that under/over-matches is a helper patch, not a policy change.
