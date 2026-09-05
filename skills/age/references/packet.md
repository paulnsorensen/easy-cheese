# Shared context packet

The orchestrator assembles this packet once per fan-out run and writes it to `.cheese/age/<slug>-packet.md`.
Each lens worker reads the full packet.
Each worker owns a `lenses[i]` entry that holds up to three dimensions.
No persistent cross-run cache exists.
Every run rebuilds the packet.
A rebuild keeps the evidence current, so no worker reads stale context.

## Components (eight, in assembly order)

1. **Located spec** — Give the path and the content of the specification or issue that `SKILL.md § Flow` step 1 identifies. Omit this component when the review has no specification.
2. **Dependency manifest contents** — `package.json`, `Cargo.toml`, `pyproject.toml`, or an equivalent file for the project under review.
3. **Project-helper index** — Detect the project source roots first. Read them from the build manifest, or fall back to the directories that the diff touches. Then search those roots for the helper names that this task needs, such as `sanitize`, `validate`, `escape`, `retry`, or `logger`. Add the task-specific candidates that the diff implies. Workers use the results to flag a not-invented-here finding or a missing helper.
4. **Path-context map** — Map which entrypoints are non-interactive or hot. Include servers, daemons, CLI handlers, and outbound callers. Workers use this map for location classification and telemetry coverage.
5. **Per-lens rubric slice and shared formula sections** — Give the assigned lens its rubric slice. Include the union of the dimension rubrics for every dimension in `lenses[i]` from `dimensions.md`. Extract each dimension from its `### <dimension>` heading to the next `###` or `##` heading. Concatenate the extracted sections. Then add `dimensions.md § Location sensitivity`, `§ Fix-cost-now`, and `§ Fix-cost-later`. Each worker computes severity from these sections alone.
6. **The severity machinery** — Include the full `§ Severity computation` section.
7. **Output contract** — Include the per-finding fields table and the exact finding format from `SKILL.md § Output`. Also include the `also-relevant-to: [<dim>, ...]` field from Seam 3. This field carries the cross-dimension signal that Seam 4 consumes. `§ Output` omits the field, so a worker that reads only `§ Output` drops it. Each worker emits full per-finding rows plus `also-relevant-to`.
8. **Dedup-ownership statement** — State that workers do not deduplicate findings or apply boundary tiebreakers.
   State that workers do not reconcile severity or write the report.
   The orchestrator owns those steps (Seam 4).
   It reconciles findings across lenses and dimensions.

## Orientation and citations block

The review-context sub-agent supplies the orientation block and the citations block.
`SKILL.md § Sub-agent fan-out` defines that worker.
Embed its digest in the packet.
Do not copy or rebuild that digest.

## Transient file contract

- Write the packet to `.cheese/age/<slug>-packet.md` before the `review-lock` capture.
- The review lock covers the packet. Do not change the packet after the lock.
- Give workers read-only access. Workers never write or modify the packet.
- Do not persist the packet across runs. Do not keep a cross-run cache. Leave cleanup to normal `.cheese/` cleanup.

## Evidence tools and fallbacks

Call source-code backends directly according to the shared [`code-intelligence-routing.md`](../../cheese/references/code-intelligence-routing.md) contract. For caller graphs, use the selected semantic backend's caller query plus `tilth_deps` when available.

| Need | Prefer | Fallback |
| --- | --- | --- |
| Diff inspection | `delta` | `git diff --unified=3` |
| Caller/dependency impact + curated review context | semantic caller search + `tilth_deps` | manual scoping; note the precision loss |
| Architecture / hotspot framing for large diffs | changed-file map + caller/dependency evidence | skip and note in confidence |
| Design rationale for the encapsulation dimension and the spec dimension (optional) | `mcp__hallouminate__list_corpora`, then `mcp__hallouminate__ground` on `repo:<repo>:wiki` | skip the wiki. Omit `## Wiki context`. Use the diff and the code as the only evidence |

Ground the design intent before you grade a finding.
List each consulted page in `## Wiki context`.
Set confidence to `speculating` when design rationale is the primary evidence.
| GitHub/PR context | `gh` | local git commands or user-provided PR data |
| Merge/conflict awareness | mergiraf | manual conflict checks |

**Optional MCPs:** hallouminate and milknado follow the detect-and-degrade contract in [`../../cheese/references/optional-plugins.md`](../../cheese/references/optional-plugins.md).
State each absence once.
Use a fallback when an optional MCP is unavailable.
Reduce confidence only when evidence quality suffers.
Never block.
