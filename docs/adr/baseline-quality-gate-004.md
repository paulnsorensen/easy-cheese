# ADR — baseline-quality-gate-004

### ADR-004: Bounded collateral-repair authority  [status: accepted]

- **Context:** Cook halts when a fix is "outside the cooked contract" — so collateral breakage the cook itself caused stops the run instead of getting repaired (user report 2026-07-22, on top of #298).
- **Decision:** New/changed failures get fixed by the cook: up to 2 fix rounds per gate, a no-progress check (same failure signature twice consecutively → halt), collateral repairs allowed freely with each recorded in Files-changed with reason. Halt only on exhaustion, no-progress, or design-shaped fixes. Policy lands once in `skills/cook/references/quality-gates.md`, consumed by press/cure/ultracook.
- **Alternatives:** Separate commit for collateral repairs (rejected: reviewability handled by report recording); test-file-only authority (rejected: production collateral exists); no-progress-only or cap-only loops (rejected: each misses the other's failure mode).
- **Consequences:** Cooks work through breakage instead of halting; the cap keeps a non-converging fix from looping — mirrors the two-cure-pass cap pattern.
