# ADR: Repair merges as an independent PR from main; mechanical intertangle fallback  [status: accepted]

Spec: baseline-repair-pathway (durable specs corpus).

- **Context:** Issue #304 mandates explicit merge order between the repair and the run. The debt lives on main (pre-existing failures), independent of the spec work, so the repair's natural base is main — but the two diffs can collide.
- **Decision:** Default: the repair worktree branches from `origin/main` and plates its own independent PR; the only coupling is the `repair_dispatch` link. Fallback fires on a mechanical intertangle test (repair diff ∩ run diff share ≥1 file — curd criterion 4 applied at merge time): a small repair (≤2 files and ≤50 changed lines) harvests into the run branch; a larger one restacks with the repair as the base PR. A failed/halted/in-flight repair never blocks the run — the debt stays recorded and the orchestrator never waits at run end (link + pasteurize slug are the resume path).
- **Alternatives:** Always harvest into the run (mixes concerns in review; a wrong repair drags the spec PR); always stack repair-first (structurally explicit order but a stuck repair blocks the spec, violating never-blocks). User chose B-default with size-directed fallback.
- **Consequences:** Clean review separation in the common case; two PRs to shepherd. The thresholds are mechanical and vetoable; topology is decided at plate time, not dispatch time.
