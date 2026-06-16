# Shared context packet

The orchestrator assembles this packet once per fan-out run and writes it to `.cheese/age/<slug>-packet.md`. Each per-dimension worker reads the full packet. There is no persistent cross-run cache — every run rebuilds (staleness risk + YAGNI).

## Components (eight, in assembly order)

1. **Located spec** — path + content, resolved via the spec-resolution order in `SKILL.md § Inputs`.
2. **Dependency manifest contents** — `package.json`, `Cargo.toml`, `pyproject.toml`, or equivalent for the project under review.
3. **Project-helper index** — one `tilth_search` for `sanitize / validate / escape / safe / retry / debounce / logger` across `src/` and `shared/`, so workers can flag NIH or missing helper usage.
4. **Path-context map** — which entrypoints are non-interactive or hot (servers, daemons, CLI handlers, outbound callers); workers need this for location classification and telemetry coverage.
5. **Per-dimension rubric slice + shared formula sections** — the worker's assigned dimension rubric from `references/dimensions.md`, plus `§ Location sensitivity`, `§ Fix-cost-now`, and `§ Fix-cost-later` so each worker can compute severity independently.
6. **The severity machinery** — the full `§ Severity computation` section.
7. **Output contract** — the per-finding fields table and finding format from `SKILL.md § Output`, so workers emit full per-finding rows the orchestrator can parse unambiguously.
8. **Dedup-ownership statement** — explicit: workers do NOT dedup, apply boundary tiebreakers, reconcile severity across dimensions, or write the report. The orchestrator owns those steps (Seam 4).

## Orientation and citations block

The existing review-context sub-agent (`SKILL.md § Sub-agent context gate`) is reused as the packet's orientation + citations block. Its digest is embedded in the packet — not duplicated or re-generated.

## Transient file contract

- Written to `.cheese/age/<slug>-packet.md` at the start of each fan-out run.
- Read-only for workers; never written or modified by workers.
- Not persisted across runs — no cross-run cache. Leave to normal `.cheese/` cleanup.
