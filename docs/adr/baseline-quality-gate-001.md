# ADR — baseline-quality-gate-001

### ADR-001: Frame-owned baseline capture  [status: accepted]

- **Context:** #298 needs a pre-implementation baseline to classify failures. Eager-always makes every cook pay broad-suite runtime up front; lazy-always doubles the failing-suite cost mid-cook and risks signature drift for environment-sensitive flakes (the observed case).
- **Decision:** Ultracook captures the baseline once per run before any curd cooks and hands it down; bare `/cook` without a frame captures lazily from the pre-change tree on first red broad gate.
- **Alternatives:** Eager-always (rejected: cost on the green path); lazy-always (rejected: mid-cook tree gymnastics as the common case).
- **Consequences:** Amortized, deterministic for the common ultracook path; the lazy fallback remains the trickiest code path but the rare one.
