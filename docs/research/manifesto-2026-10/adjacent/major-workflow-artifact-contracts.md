# Research: artifact contracts in major agent workflows

Checked: 2026-10-04.
Thread: easy-cheese-contracts-simplify.
Scope: public documentation and upstream templates, not private storage implementations or an adoption ranking.

## Finding

Distinct specifications and implementation plans have strong precedent.
The examined workflows do not converge on one storage model or a universal Spec, Plan, Review schema family.
Most inspected artifacts are Markdown documents with prescribed content.
That is evidence for semantic separation, not necessarily for machine-validated payload schemas.

Review has several representations.
Spec Kit has requirements-quality checklists.
BMAD appends code-review evidence to a ticket plan.
Superpowers returns reviewer findings.
Devin offers a PR review surface and user-defined structured session output.
These are different contracts, not interchangeable meanings of review.[^checklist][^bmad-review][^super-review][^devin][^devin-json]

Separate contracts therefore do not require separate top-level work records.
OpenSpec groups distinct artifacts under one change directory.
Backlog.md embeds an implementation plan in a task.
Beads supports embedded acceptance/design fields and a specification link.[^openspec][^backlog][^beads]

The user's leaning remains separate Spec, Plan, and Review contracts.
Whether these are embedded or linked remains open.
This report makes no storage decision.

## Terms used in this comparison

- Semantic contract: the meaning and required content of an artifact.
- Payload schema: a machine-readable definition of its fields and validation.
- Container: a feature directory, change directory, task, or session that groups related artifacts.
- Workflow: the operations and ordering rules that produce or consume artifacts.

An artifact-production schema is not automatically a payload schema.
A folder is not evidence of a database record type.
A review operation is not evidence of a standalone review file.

## Claim evidence table

| Claim | Evidence | Source type | Freshness | Confidence | Caveat |
| --- | --- | --- | --- | --- | --- |
| Kiro separates requirements or bug analysis, technical design, and implementation tasks. | raw/a-01-kiro-specs.md lines 5-14 [^kiro] | Vendor docs | 2026-10-04 | certain | Public files, not internal record types. |
| Kiro Quick Spec retains the same three files while removing intermediate approval gates. | raw/a-02-kiro-quick.md lines 5-14 [^kiro-quick] | Vendor docs | 2026-10-04 | certain | Its separate Vibe mode saves no spec artifacts. |
| Spec Kit groups spec, plan, tasks, and supporting design documents by feature directory. | raw/a-03-speckit-quickstart.md lines 5-14; raw/a-05-speckit-plan-template.md lines 5-9 [^speckit][^plan-template] | Upstream docs/templates | 2026-10-04 | certain | Plan means technical approach; executable tasks are a further artifact. |
| Spec Kit's spec template has scenarios, requirements, and success criteria; its task template has task IDs, story tags, paths, and dependencies. | raw/a-04-speckit-spec-template.md lines 5-12; raw/a-06-speckit-tasks-template.md lines 5-9 [^spec-template][^tasks-template] | Upstream templates | 2026-10-04 | certain | Markdown structure does not establish a public JSON payload schema. |
| Spec Kit domain checklists review requirements quality, not code completion. Its analysis operation compares spec, plan, and tasks without modifying them. | raw/a-07-speckit-checklist.md lines 5-7; raw/a-03-speckit-quickstart.md lines 11-14 [^checklist][^speckit] | Upstream command/docs | 2026-10-04 | certain | Do not treat checklist approval as implementation evidence. |
| OpenSpec's default spec-driven schema groups proposal, delta specs, design, and tasks under one named change directory. | raw/b-01-openspec-spec-driven.md lines 3-8 [^openspec] | Upstream docs | 2026-10-04 | certain | The schema defines artifact production and templates. It is not proof of formal schemas for all artifact bodies. |
| OpenSpec's default graph permits conditional omission of design and specs. | raw/b-01-openspec-spec-driven.md lines 3-7 [^openspec] | Upstream docs | 2026-10-04 | certain | Optional artifacts do not mean zero dependency rules. |
| BMAD varies planning depth and groups documents by initiative or output directory. | raw/b-04-bmad-planning-path.md lines 3-6 [^bmad-plan] | Official docs | 2026-10-04 | certain | This describes the fetched public workflow, not every version or fork. |
| BMAD code review appends a dated review block to the ticket plan without changing ticket status. | raw/b-05-bmad-stories-review.md lines 3-5 [^bmad-review] | Official docs | 2026-10-04 | certain | Distinct review meaning, embedded review storage. |
| Superpowers' architectural path writes separate specification and plan files. Its bounded path uses an approved chat design without a plan document. | raw/b-06-superpowers-plan.md lines 3-4; raw/b-07-superpowers-brainstorm.md lines 3-5 [^super-plan][^super-spec] | Upstream skills | 2026-10-04 | certain | Separate sibling directories, not a demonstrated universal work-record schema. |
| Superpowers passes plan/requirements and a commit range to a reviewer. | raw/b-08-superpowers-code-review.md lines 3-5 [^super-review] | Upstream skill | 2026-10-04 | certain | A persistent review-file path was not found in this inspected skill; that absence is speculating. |
| Devin accepts a pasted spec and carries implementation, verification, and follow-up work through a session and PR. | raw/c-01-devin-feature-spec.md lines 4-8 [^devin] | Vendor docs | 2026-10-04 | certain | No inference about private storage tables or artifact revision IDs. |
| Devin permits user-defined structured session output, including example review and progress fields. | raw/c-03-devin-structured-output.md lines 4-8 [^devin-json] | Vendor API docs | 2026-10-04 | certain | Example fields are not a vendor-mandated Review contract. |
| Backlog.md writes the implementation plan inside the task while distinguishing spec, plan, and code review checkpoints. | raw/e-cached-backlog.md lines 3-8 (original lines 36-46, 140-155) [^backlog] | Cached upstream README | 2026-10-04 | certain | Three checkpoints do not prove three payload schemas. |
| Beads embeds acceptance/design information and supports a specification link on issues. | raw/e-cached-beads.md lines 3-8 (original lines 475-516) [^beads] | Cached upstream command reference | 2026-10-04 | certain | Field-level precedent, not evidence for a Spec/Plan/Review contract family. |

## What changes the earlier discussion

The previous either/or framing was too coarse.
A common record container and separate payload contracts can coexist.
The examples above establish this distinction without selecting an easy-cheese representation.

The evidence for separating specification from implementation planning is stronger than the evidence for a universal standalone Review artifact.
Review can mean requirements inspection, implementation findings, verification results, or approval.
The inspected tools represent those meanings differently.

Planning also has more than one meaning.
Kiro and Spec Kit distinguish technical design from the executable task list.[^kiro][^plan-template][^tasks-template]
This distinction matters when deciding what easy-cheese calls Plan.

Removing gates does not require removing artifact boundaries.
Kiro Quick Spec demonstrates that directly.[^kiro-quick]
Conversely, Superpowers' bounded path demonstrates that some work can omit a plan document.[^super-spec]

## Prior research onboarding and corrections

The parent read the prior context-compilation report, rebuild report, and relevant session notes.
A dedicated researcher audited all 24 files in the context-compilation raw directory by full reads or task-relevant sections.
The audit also inspected seven relevant rebuild captures.
The long Beads CLI reference was not read end-to-end.
Optimization benchmarks outside this decision were not audited.
The exact inventory and limitations are in raw/d-prior-audit.md.

Several prior captures are brief WebFetch summaries, not full source bodies.
The prior ADK, Manus, LangChain, ACE, CodeNib, and TDS material does not establish Spec/Plan/Review storage contracts.
Those sources remain context-compilation analogies, not answers to this artifact question.

The earlier claim that OpenSpec is the only phase-free tool is not supported by that survey.
The earlier delivery-planning absence claim also exceeds the inspected material.
Taskmaster's automatic complexity-based plan scaling remains an inference.
The Beads architecture capture is a 404 and supports no claim.

The earlier report remains unchanged as a historical artifact.
This report supersedes those broad conclusions only within the scope stated above.

## Open questions

- Does Plan contain technical design, executable tasks, or both? — speculating.
- Does Review represent findings only, or also coverage and verification evidence? — speculating.
- Should each payload have its own identity and revision, while a work record links them? — speculating.
- Can small payloads remain embedded without changing their semantic contracts? — speculating.

These are local design choices.
The survey does not supply a consensus that resolves them.

## Coverage and confidence

Overall: speculating.
Primary sources establish the positive workflow claims.
The fit to easy-cheese and private storage implementations remain unproven.

Factory returned relevant search results, but no usable page.
Native web retrieval failed on both documentation hosts.
A direct HTTP fallback failed DNS resolution.
No Factory schema claim appears in the findings.

Agent OS was not researched beyond the prior digest.
No market-share or adoption data was collected.
No claim describes what all major tools do.

## Routing

- Library/API documentation: NO as a separate provider lane; public documentation uses the current-web lane.
- Current-web discovery/extraction: YES, native web.
- Repository knowledge: YES, prior reports, captures, and session notes.
- Local code intelligence: NO, no new source-code claims.
- Git hosting/examples: YES, upstream documents and templates through native web.
- Factory fallback: direct HTTP through curl; failed DNS.

## agent_resolution

```yaml
agent_resolution:
  request:
    work: fetch and synthesize independent workflow evidence and audit prior captures
    preferred_types: [researcher]
    required_tools: [web-search-open, tilth-read, tilth-write]
    permissions: write
    isolation: fresh-context
    minimum_power: default
    effort: medium
  attempts:
    - type: researcher
      model: gpt-6-sol
      power: default
      result: accepted
      reason: exact specialist; writes restricted by dispatch to distinct research prefixes
  resolved:
    type: researcher
    model: gpt-6-sol
    power: default
    effort: medium
    topology: fan-out-fan-in
  fallback_reason: null
  degraded: false
  permission_enforcement: tool-restricted
```

Four fresh-context researchers use separate artifact prefixes.
They share no source-code edit scope.
The parent owns this report and the combined claim table.
The tool sandbox permits artifact writes; prefix ownership is prompt-defined, not an independent filesystem boundary.

## Verification log

- Worker ledgers recorded provider calls during collection; the parent combined them into manifest.json.
- URL digests were recomputed with hashlib before integration.
- The parent checked the captured passages for the central comparison claims.
- Captures contain selected excerpts or attributed summaries with upstream line references, not complete page archives.
- A partial Spec Kit analyze retrieval is not evidence. The analysis claim uses the retrieved quickstart instead.
- Initial budget-check found a partial capture marked as evidence; the combined manifest now omits its evidence path.
- The ledger retains a duplicate Devin URL retrieval used for a later line range. It is not relabeled as a freshness check.
- Collection used 12 searches, 25 fresh retrieval attempts, three cached captures, and four fresh-context researchers.
- Ground-check: zero errors and three reviewed absence advisories. Cross-directory cache pointers now use local attributed excerpt summaries.
- Budget-check retains one DUPLICATE_EXTRACT finding for the deliberate Devin range continuation. This process finding is not hidden.
- The three absence advisories concern explicit source statements: read-only analysis, unchanged ticket status, and the bounded path omitting a plan document.
- No repository source changed. Code tests and just check are skipped for this read-only repository research.

## Next step

Return to /culture with separate artifact contracts and storage identity as separate design questions.

## References

[^kiro]: https://kiro.dev/docs/specs/ (fetched 2026-10-04).
[^kiro-quick]: https://kiro.dev/docs/specs/quick-spec/ (fetched 2026-10-04).
[^speckit]: https://github.com/github/spec-kit/blob/main/docs/quickstart.md/ (fetched 2026-10-04).
[^spec-template]: https://github.com/github/spec-kit/blob/main/templates/spec-template.md (fetched 2026-10-04).
[^plan-template]: https://github.com/github/spec-kit/blob/main/templates/plan-template.md (fetched 2026-10-04).
[^tasks-template]: https://github.com/github/spec-kit/blob/main/templates/tasks-template.md (fetched 2026-10-04).
[^checklist]: https://github.com/github/spec-kit/blob/main/templates/commands/checklist.md (fetched 2026-10-04).
[^openspec]: https://github.com/Fission-AI/OpenSpec/blob/main/docs-lab/reference/schemas/spec-driven/index.md (fetched 2026-10-04).
[^bmad-plan]: https://docs.bmad-method.org/cs/plan/choose-a-planning-path/ (fetched 2026-10-04).
[^bmad-review]: https://docs.bmad-method.org/plan/break-work-into-stories-and-track-it/ (fetched 2026-10-04).
[^super-plan]: https://github.com/obra/superpowers/blob/main/skills/writing-plans/SKILL.md (fetched 2026-10-04).
[^super-spec]: https://github.com/obra/superpowers/blob/main/skills/brainstorming/SKILL.md (fetched 2026-10-04).
[^super-review]: https://github.com/obra/superpowers/blob/main/skills/requesting-code-review/SKILL.md (fetched 2026-10-04).
[^devin]: https://docs.devin.ai/use-cases/gallery/implement-feature-from-spec (fetched 2026-10-04).
[^devin-json]: https://docs.devin.ai/api-reference/v1/structured-output (fetched 2026-10-04).
[^backlog]: https://github.com/MrLesk/Backlog.md (cached upstream README fetched 2026-10-04).
[^beads]: https://github.com/steveyegge/beads/blob/main/docs/CLI_REFERENCE.md (cached upstream command reference fetched 2026-10-04).
