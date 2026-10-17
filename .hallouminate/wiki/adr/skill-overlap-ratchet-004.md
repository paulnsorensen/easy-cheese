# ADR: Ratchet reviewed content-specific overlap findings

The job begins advisory, then blocks only new content-specific exact or high-confidence semantic findings against a reviewed baseline; aggregate duplication totals never decide pass or fail.

## Decision record

### ADR-004: Reviewed findings and dual calibrated thresholds [status: accepted]

- **Context:** Aggregate budgets allow new duplication to hide behind unrelated cleanup. Stable section-pair allowances can hide additional repetition added to an already accepted pair. A single sensitive semantic threshold creates false positives, while one strict threshold loses useful consolidation candidates.
- **Decision:** Fingerprint findings from detector and model metadata, unordered source endpoints, and normalized content hashes. Calibrate a blocking threshold and a lower advisory threshold from labeled corpus pairs. Require every accepted blocker to be checked into Git as `intentional` or `debt` with a reason. Keep frontmatter similarity in a separate advisory lane.
- **Alternatives:** Aggregate duplicated-token budgets; stable section-pair allowances; one semantic threshold; semantic reporting without enforcement; automatic accept-all baseline generation.
- **Consequences:** New duplicated content cannot be offset or hidden, and medium-confidence overlap remains visible without destabilizing CI. Small edits to accepted repetition can require renewed review. Detector, model, tokenizer, chunker, or calibration changes require explicit rebaseline.

Related: [[skill-overlap-ratchet-001]], [[skill-overlap-ratchet-003]].
