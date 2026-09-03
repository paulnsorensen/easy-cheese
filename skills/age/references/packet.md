# Shared context packet

The orchestrator assembles this packet once per fan-out run and writes it to `.cheese/age/<slug>-packet.md`.
Each lens worker reads the full packet.
Each worker owns a `lenses[i]` entry that may bundle up to three dimensions.
No persistent cross-run cache exists.
Every run rebuilds the packet, which creates staleness risk and avoids YAGNI.

## Components (eight, in assembly order)

1. **Located spec** — path + content, resolved through the spec-resolution order in `SKILL.md § Inputs`.
2. **Dependency manifest contents** — `package.json`, `Cargo.toml`, `pyproject.toml`, or an equivalent file for the project under review.
3. **Project-helper index** — Run one `tilth_search` for `sanitize / validate / escape / safe / retry / debounce / logger` across `src/` and `shared/`. Workers use the results to flag NIH or missing helper usage.
4. **Path-context map** — Map which entrypoints are non-interactive or hot. Include servers, daemons, CLI handlers, and outbound callers. Workers use this map for location classification and telemetry coverage.
5. **Per-lens rubric slice + shared formula sections** — Provide the assigned lens's rubric slice and the shared formula sections. Include the union of the dimension rubrics for every dimension in `lenses[i]` from `dimensions.md`. Include `§ Location sensitivity`, `§ Fix-cost-now`, and `§ Fix-cost-later` so each worker can compute severity independently. Extract each dimension's `## <Dimension name>` heading to the next `##` heading. Concatenate the extracted sections.
6. **The severity machinery** — Include the full `§ Severity computation` section.
7. **Output contract** — Include the per-finding fields table and finding format from `SKILL.md § Output`. Also include the `also-relevant-to: [<dim>, ...]` field from Seam 3. This field carries the cross-dimension signal that Seam 4 reconciliation consumes. It is not part of `§ Output`'s base format, so a worker that follows only `§ Output` would omit it. Workers emit full per-finding rows with the format fields and `also-relevant-to`. The orchestrator can parse and reconcile those rows without ambiguity.
8. **Dedup-ownership statement** — State that workers do not deduplicate findings or apply boundary tiebreakers.
   State that workers do not reconcile severity or write the report.
   The orchestrator owns those steps (Seam 4).
   It reconciles findings across lenses and dimensions.

## Orientation and citations block

The existing review-context sub-agent (`SKILL.md § Sub-agent context gate`) supplies the packet's orientation + citations block.
Embed its digest in the packet.
Do not duplicate or regenerate it.

## Transient file contract

- Write the packet to `.cheese/age/<slug>-packet.md` at the start of each fan-out run.
- Give workers read-only access. Workers never write or modify the packet.
- Do not persist the packet across runs. Do not keep a cross-run cache. Leave cleanup to normal `.cheese/` cleanup.
