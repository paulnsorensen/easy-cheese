# ADR — baseline-quality-gate-002

### ADR-002: baseline: block, not a new status enum  [status: accepted]

- **Context:** #298 floated `ok_with_baseline_failures`. A new enum value ripples through the table-driven decision engine (`src/fanout/phase_decision.py`) and every status consumer.
- **Decision:** Statuses stay `ok`/`halt`; the handoff slug and run manifest gain an optional, additive `baseline:` block (fingerprinted failures + classification) that phases and `/cheese --continue` read. `validate_run_manifest` gates the block's schema.
- **Alternatives:** New status (rejected: engine + consumer blast radius); both (rejected: redundant).
- **Consequences:** Engine untouched; "ok" can now mean "ok with recorded debt" — mitigated by the mandatory final-summary rule ("full suite is not green") so the debt is never silent.
