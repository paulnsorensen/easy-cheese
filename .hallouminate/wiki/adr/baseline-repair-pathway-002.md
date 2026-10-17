# ADR: Repair consent is automatic under --auto, prompted at record time otherwise  [status: accepted]

Spec: baseline-repair-pathway (durable specs corpus).

- **Context:** Issue #304's acceptance says "the user can opt into" the repair dispatch, but `--auto` runs cannot prompt mid-run. Candidate shapes: an invocation flag (`--fix-baseline`), a record-time prompt, or a layered combination.
- **Decision:** Under `--auto`, the frame dispatches the repair automatically — `--auto` itself is the standing consent. Interactive runs get a record-time prompt when identical-to-baseline failures are first recorded (ultracook: pre-Seed; bare cook: first red broad gate).
- **Alternatives:** Flag-only (commits the user before knowing debt exists); prompt-only (autonomous runs silently never repair); flag+prompt layering (more spec surface). User chose auto-implies-consent + prompt.
- **Consequences:** Zero new flags; autonomous runs always work the debt. Cost is bounded by the dedupe rule (never dispatch when a live `repair_dispatch` link exists). A `--no-fix-baseline` opt-out was explicitly deferred as a non-goal (no artifact) until an `--auto` user actually wants to skip repairs.
