# Research: context compilation over typed work records

Thread: `easy-cheese-contracts-simplify` (forked from `rebuild-easy-cheese-from-scratch`).
Checked: 2026-10-04.

## Finding

No surveyed source combines all three parts of the proposed model: a typed ontology of work records, per-task compilation of agent context from those records, and no fixed phase pipeline.
Each part exists separately.
Google ADK states the compilation thesis most directly: "context is a compiled view over a richer stateful system", built from typed Event records by ordered processors [^adk].
Its unit is a session event, not a work item.
Beads models work as a typed issue graph with ten dependency edge kinds and projects ready work to agents through `bd ready` and `bd show` [^beads].
It uses no "compile" framing.
OpenSpec is the only spec-driven tool that is phase-free ("Dependencies are enablers, not gates"), has a lite path for most changes, and keeps a living spec by merging change deltas at archive time [^openspec].
Its artifacts are freeform markdown.

The two user-supplied "context compiler" sources are narrower than their titles.
project-context/context-compiler is a README-only concept with a typed block graph (requirement, decision, design spec, API contract, test, bug, risk) and role and task views [^pcc].
It has no code, no schema, and no plan model.
The Towards Data Science article describes a code-only compiler that prunes dependencies to interfaces [^tds].

Size-scaled planning appears in two places only.
OpenSpec keeps most changes in a lite mode [^openspec].
Taskmaster scores task complexity from 1 to 10 and expands subtasks against a threshold [^taskmaster].
No surveyed tool puts delivery or PR planning inside the plan artifact.
superpowers keeps branch finishing in separate skills [^superpowers].

## Evidence

| Claim | Evidence | Source type | Freshness | Confidence | Caveat |
| --- | --- | --- | --- | --- | --- |
| ADK frames context as a compiled view over typed Events, built by ordered processors per call. | raw/b-adk.md [^adk] | vendor blog | 2026-10-04 | `speculating` | Single origin; WebFetch summary, quotes not verbatim-verified. |
| Manus uses an append-only log, the file system as memory, and todo.md recitation; it gives no record schema. | raw/b-manus-langchain.md [^manus] | vendor blog | 2026-10-04 | `speculating` | Single origin. |
| LangChain names four context strategies: write, select, compress, isolate. | raw/b-manus-langchain.md [^langchain] | vendor blog | 2026-10-04 | `speculating` | Single origin. |
| CodeNib compiles per-commit code views and reports 50-87% fewer tokens than grep and read. | raw/b-ace-codenib.md [^codenib] | paper | 2026-10-04 | `speculating` | Figure from a fetch summary, not checked against the paper. |
| ACE evolves a playbook through generation, reflection, and curation with delta updates. | raw/b-ace-codenib.md [^ace] | paper | 2026-10-04 | `speculating` | Abstract only. |
| project-context/context-compiler is README-only: 2 files, 5 stars, no license, last commit 2026-06-02. | raw/a-tree.txt, raw/a-repo.json, raw/a-commit.json [^pcc] | Git host | 2026-10-04 | `certain` | Host metadata is authoritative for hosted state. |
| Its README defines a typed block ontology, link types, and an Ingest-to-Emit pipeline with role and task views. | raw/a-readme.md#L340-L502 [^pcc] | Git host | 2026-10-04 | `certain` | Illustrative only; no implementation. |
| The TDS compiler is code-only: symbol resolution, interface extraction, tiered assembly; it self-reports 69-74% prompt reduction. | raw/a-tds-article.md [^tds] | blog | 2026-10-04 | `speculating` | Self-reported; repo link elided in extract. |
| OpenSpec is phase-free, has a lite path, and merges ADDED/MODIFIED/REMOVED deltas into main specs on archive. | raw/c-01-openspec-concepts.md [^openspec] | vendor docs | 2026-10-04 | `certain` | Primary docs for its own behavior. |
| spec-kit runs a fixed chain from constitution through implement. | ../rebuild-easy-cheese-from-scratch/raw/d-02-github-spec-kit.md [^speckit] | Git host | 2026-09-21 | `certain` | Primary repo; not re-checked for October changes. |
| Böckeler finds spec-kit ceremony too heavy for a 3-5 point story. | ../rebuild-easy-cheese-from-scratch/raw/e-04-martinfowler.com.md [^fowler] | blog | 2026-09-21 | `speculating` | Single practitioner report. |
| Kiro uses three fixed phases: requirements, design, tasks. | ../rebuild-easy-cheese-from-scratch/raw/d-10-kiro-docs-specs.md [^kiro] | vendor docs | 2026-09-21 | `certain` | Primary docs. |
| superpowers keeps worktree and branch-finishing skills separate from the plan. | ../rebuild-easy-cheese-from-scratch/raw/d-01-github-obra-superpowers.md [^superpowers] | Git host | 2026-09-21 | `certain` | Primary repo. |
| Cursor plan mode saves a plan file to the home directory with optional save to workspace; delivery is not found in the fetched page. | raw/c-03-cursor-plan-mode.md [^cursor] | vendor docs | 2026-10-04 | `speculating` | Stated behavior only. |
| Beads models work as an issue graph with edge kinds blocks, tracks, related, parent-child, discovered-from, until, caused-by, validates, relates-to, supersedes. | raw/d-beads-CLI_REFERENCE.md [^beads] | Git host | 2026-10-04 | `certain` | Issue-type enum and schema not extracted. |
| Beads projects work to agents through a ready queue and show/claim commands, and compacts closed issues into summaries. | raw/d-beads-readme.md [^beads] | Git host | 2026-10-04 | `certain` | Primary repo. |
| Taskmaster scores complexity 1-10 with a threshold and expands subtasks; default expansion count follows the complexity report. | raw/d-tm-cmdref.md [^taskmaster] | Git host | 2026-10-04 | `speculating` | Default behavior inferred from help text. |
| Agent decision records are injected manually through CLAUDE.md instructions, not compiled. | raw/d-calls.jsonl [^agdr] | blog | 2026-10-04 | `speculating` | Search snippets only. |
| No surveyed tool puts delivery or PR planning in the plan artifact. | raw/c-01-openspec-concepts.md, ../rebuild-easy-cheese-from-scratch/raw/d-01-github-obra-superpowers.md, ../rebuild-easy-cheese-from-scratch/raw/d-02-github-spec-kit.md, raw/c-03-cursor-plan-mode.md | mixed | 2026-10-04 | `speculating` | Absence across the surveyed tools only; Devin, Factory, Agent OS not checked. |
| No surveyed source combines typed work records, per-task compilation, and no fixed phases. | raw/b-adk.md, raw/d-beads-readme.md, raw/c-01-openspec-concepts.md, raw/a-readme.md | mixed | 2026-10-04 | `speculating` | Absence across the surveyed sources only. |

## Mapping to easy-cheese (evidence only)

| Source idea | Nearest easy-cheese element |
| --- | --- |
| ADK compiled view over typed records | Wheypoint record as the stateful store; a per-task projection as the compiled view. |
| Beads edge vocabulary and ready queue | `WorkEdge` kinds (implements, informs, blocked_by, supersedes) and milknado ready nodes. |
| OpenSpec delta merge into a living spec | The parent thread's open fork on the living-spec artifact shape. |
| Taskmaster complexity-scaled expansion | The proposed plan that is omitted, inline, or full by size. |
| project-context typed blocks with validate pass | Contract validation in `easy_cheese_schemas`. |

## Open questions

- Is the compiled context a projection of the wheypoint graph, as in ADK, or a ready-queue selection, as in Beads? `speculating`
- Does plan weight scale by a code-scored complexity, as in Taskmaster, or by a user or agent choice, as in OpenSpec lite? `speculating`
- Does the spec live as merged deltas, as in OpenSpec, or as a document patched in place? `speculating`
- Does delivery belong inside the plan, given that no surveyed tool does this? `speculating`

## Confidence

`speculating` — Primary sources cover OpenSpec, Kiro, spec-kit, Beads, and project-context; the central absence claim covers only the surveyed sources.

## Next step

Return to `/culture` on `easy-cheese-contracts-simplify` for the ontology and plan-scaling forks.

## Searched, empty

- Current web via Tavily, "context compilation coding agent" and related arXiv queries → no source with typed work records plus compilation.
- DSPy, Letta memory blocks, Mikado graphs for agents, Devin, Factory, and Agent OS docs → not searched within budget.

## agent_resolution

| Work | Agent | Count |
| --- | --- | --- |
| Fetch and synthesize one heavy source group | researcher | 4, parallel |

## References

[^adk]: https://developers.googleblog.com/architecting-efficient-context-aware-multi-agent-framework-for-production/ (fetched 2026-10-04).
[^manus]: https://manus.im/blog/Context-Engineering-for-AI-Agents-Lessons-from-Building-Manus (fetched 2026-10-04).
[^langchain]: https://www.langchain.com/blog/context-engineering-for-agents (fetched 2026-10-04).
[^codenib]: https://arxiv.org/abs/2607.25431 (fetched 2026-10-04).
[^ace]: https://arxiv.org/abs/2510.04618 (fetched 2026-10-04).
[^pcc]: https://github.com/project-context/context-compiler (fetched 2026-10-04).
[^tds]: https://towardsdatascience.com/coding-agents-dont-need-bigger-context-windows-they-need-a-context-compiler/ (fetched 2026-10-04).
[^openspec]: https://github.com/Fission-AI/OpenSpec/blob/main/docs/concepts.md (fetched 2026-10-04).
[^speckit]: https://github.com/github/spec-kit (fetched 2026-09-21).
[^fowler]: https://martinfowler.com/articles/exploring-gen-ai/sdd-3-tools.html (fetched 2026-09-21).
[^kiro]: https://kiro.dev/docs/specs (fetched 2026-09-21).
[^superpowers]: https://github.com/obra/superpowers (fetched 2026-09-21).
[^cursor]: https://cursor.com/docs/agent/plan-mode (fetched 2026-10-04).
[^beads]: https://github.com/steveyegge/beads (fetched 2026-10-04).
[^taskmaster]: https://github.com/eyaltoledano/claude-task-master (fetched 2026-10-04).
[^agdr]: https://github.com/me2resh/agent-decision-record [unverified] (search snippet 2026-10-04).
