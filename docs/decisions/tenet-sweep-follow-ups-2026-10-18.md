# Tenet sweep follow-ups: what is next to decide (2026-10-18)

This page is a reviewable snapshot of the wheypoint handoff `tenet-sweep-follow-ups` at revision `rev-1c27a4a21499` (record digest `sha256:b94fe7dc28889af796c9526a164b9a669a4139078b8eaa7e545083418fc34f3a`, schema 5). The record under `.cheese/notes/` stays authoritative and resumes with `/cheese --continue tenet-sweep-follow-ups`. The owner asked for this snapshot as a pull request so the open decisions can be read and discussed in one place.

Context: on 2026-10-18 the 23 open pull requests listed against the tenets in #828 and #829 were reviewed and either merged (11), closed with evidence (11), or held (#358). The owner then ruled on five of the ten lettered forks from #829 `docs/architecture/manifesto-evidence.md` section 5. What follows is what remains open, what was ruled, what is in flight, and the evidence behind it.

## Next to decide

### Fork D: the six Stream forks

Recorded in the rebuild session of 2026-10-03 (copied into #829 under `docs/research/manifesto-2026-10/rebuild/session-2026-10-03-workflows-stream.md`). Rule on each; the promotion-line ruling also fixes a live conflict on `main`.

| Fork | Options | Recorded lean | On `main` today |
| --- | --- | --- | --- |
| Canvas role | feedback only, or an editing surface | feedback only | the canvas renders hand-authored JSON and returns pins and answers; it never writes the spec |
| Build | its own workflow, or a stream that starts ready | none | skills are still separate stations |
| Promotion line | cold executor or public contract, or any leverage trigger | cold executor or public contract | `skills/cheese/references/routing-policy.md:46` sends any fired trigger to full mold; `skills/mold/references/tiers.md:19` only rules Quick out |
| Inline line | risk plus size in code, risk only, or agent judgment | risk plus size in code | no inline gate exists; fork B heuristic 1 is this gate |
| Section edited under an in-flight piece | finish and queue a follow-up, or cancel and resend | finish and queue | no rule exists; fork B heuristic 4 depends on it; #828 lists it under decisions still needed |
| Workflow-list completeness | six workflows, or reconcile with the fifteen mapped on 09-24 | none | the fifteen-workflow map is unrecovered |

### Tensions between #828 and #829 without a letter

1. Canonical home for the tenets: the wiki page (#828) or `docs/manifesto.md` plus the evidence bundle (#829). AGENTS.md favors the wiki. The wording edits the rulings imply in #829 (tenet 7 as size-gated, the single-writer default replaced by the heuristics) wait on this call.
2. #829's "already decided" list against #828's "decisions still needed" list. The rulings below answer the readiness question in part; the spec-change-during-parallel-work rule is still open (it is Stream fork 5).
3. The human-altitude sentence in tenet 3: keep (#829) or remove (#828).
4. Sequencing: cut first (#829) or measure first (#828). #829's fan-out flip is gone; its one-fan-versus-single-writer measurement survives as the calibration for the size score.

### Deferred by the owner

- Fork E, skill cut list: end of this session.
- Fork F, grader design and the first live journey run: after the tilth benchmark work. PRs 822 to 825 remain open with no live run; `tools/wedge/pyproject.toml:8` still pins a `lib/` subdirectory.
- Fork G, further wheypoint cut scope: owner's call. Re-read against `main` first: #776 landed schema 5.
- Fork H, CLI shape, one archive or thirteen: owner's call. Thirteen `wedge.toml` archives today.

### Design questions the rulings opened

- Open a `/mold` for the cook size heuristics: the size score, the grounding-plan section of the spec, mixed inline and dispatched curds, the in-flight piece rule, and the degrade path on a harness without sub-agents.
- Review artifact format: which sections, who edits it, and where it lands (PR body, walkthrough comment, or a wheypoint-linked Review record).
- Config shape for the shipped defaults: file location, precedence order, and which heuristics it exposes. Precedents: spec-kit's overrides, presets, extensions, core order; OpenSpec's `openspec/config.yaml`; milknado's `~/.config/milknado/milknado.toml` preset pack.

### Administrative items awaiting an explicit yes

- Dismiss CodeQL alert 756 on #810 (pre-existing on `main`).
- Close #515 as superseded by #772 to #774.
- Delete the branch `worktree/wheypoint-contract-simplify` (its tree equals the #776 merge).
- Narrow or close issue #267.
- Review and merge #820.

### Found while grounding

`docs/architecture/milknado-semantic-boundary-reassessment.md` says to keep milknado as a consumer of `easy-cheese-schemas` that validates an imported projection. milknado's own `docs/adr/adversarial-review-loops-003.md` (accepted 2026-07-19) integrates at the artifact and format layer with no runtime coupling, and milknado's dependency list has no easy-cheese entry. The fork J ruling matches milknado's record, so this page needs reconciling.

## Ruled on 2026-10-18

| Fork | Ruling | Evidence |
| --- | --- | --- |
| A, design-target harness | Target generic agents; the harness must not matter; opinionated defaults behind a config shipped later | The Agent Skills spec has only `compatibility`, `metadata`, and an experimental `allowed-tools`, and no portability section, so capability declaration lives in the pack. `skills/cheese/references/harness-portability.md`; wiki `adr/codex-omp-portability-001`; milknado ships one plugin on Claude Code, Codex, and opencode |
| B, fan-out default | Dissolved: cook's shape follows size heuristics. Small work cooks inline when caching is cheapest; one sizeable curd gets a fresh-context handoff with its grounding plan in the spec; several curds are planned for parallel execution mixing dispatched and inline work; pieces ready during molding start at once | `skills/cook/SKILL.md` fan pathway; wiki `adr/deterministic-fanout-sizing-003` and `-004` (code decides width; a declared estimate is gated by code); `MAX_CURD_SURFACE` was never built |
| C, record ontology | Separate Spec, Plan, and Review contracts; the wheypoint record links to them as first-class citizens rather than embedding them | wiki `adr/workflow-contract-milknado-seam-001`; OpenSpec links by `requires:` ids and spec-kit by path, and both trackers name duplication and drift, so links need digest pins |
| I, reviewability artifact | hard-cheese stays as the quiz; a separate review-time artifact is still needed | wiki `adr/hard-cheese-retained-001`; no reachable primary study measures a defect-detection effect of author descriptions, so the artifact's justification is comprehension and review cost; Copilot, CodeRabbit, GitLab Duo, and Graphite all draft an author-editable PR description |
| J, milknado | milknado stays the parallel executor, consumed as an optional plugin with pointer coupling at the artifact boundary | milknado `docs/adr/adversarial-review-loops-003.md`; wiki `adr/workflow-contract-milknado-seam-006`; Shape B (runtime import, 2026-08-28) is the only recorded move that contradicts this and stays unexecuted |

## In flight

Four cook workers, one worktree and one draft pull request each, started after the rulings:

- `cook/514-transport-audit`: salvage the transport-audit check from #514.
- `cook/821-mold-review-status`: fix the mold-review status where Saved overwrites Sending.
- `cook/753-diagram-trigger`: the deterministic diagram trigger scoped in the #753 close comment.
- `cook/ci-mold-review-playwright`: a CI job that runs the mold-review Playwright suite.

Held: the #313 shared-store page from #358. hallouminate was unavailable in the session, and AGENTS.md says to skip wiki updates rather than hand-edit the indexed tree. #358 itself now re-derives from the size heuristics instead of a default flip.

## Reground

Window: `336258e0` (the base both manifesto PRs were grounded on) to `e927b604`, 11 commits and 99 files.

| Verdict | Claims |
| --- | --- |
| holds | cook fast, curded, and un-curded shapes; `MAX_CURD_SURFACE` never built; the sizing ADRs; the routing-policy versus tiers ceremony conflict; #780 altitude in culture; #809 fork cards; press per curd (786 to 788); `EdgeKind` supersedes and forked_from; hard-cheese is a quiz; plate's PR body has Non-obvious changes and a Diagram section; 13 archives; schema 5 on `main`; the wedge pin names `lib/`; PRs 822 to 825 open |
| stale | `contracts.py` is 4,274 lines, not 4,202; 29 open pull requests, not 50 |
| unverifiable from the repo | 85% of skill loads from omp; 91% of dispatches passed no model |
| not on `main` | the `file:`, `xdg:`, `wiki:`, `milknado:` ArtifactRef schemes proposed in #829 |

## Research

The cited research for A, C, I, and J lives in the durable corpus at `research/fork-rulings-2026-10-18/fork-rulings-2026-10-18.md` with its capture manifest and raw pulls. Confidence is certain for the spec, config, tooling, and milknado rows read from raw sources, and speculating for rows that came through search summaries after the egress proxy refused most primary hosts.

- Agent Skills frontmatter fields: `name`, `description`, `license`, `compatibility`, `metadata`, `allowed-tools` (experimental).
- spec-kit resolves project overrides, then presets, extensions, and core templates, and materializes command files. OpenSpec resolves a CLI flag, change metadata, project config, then the default.
- No primary study measured a defect-detection effect of author-written descriptions. Bosu, Greiler, and Bird 2015 found useful-comment density falls as files per change rise.
- milknado ships as a plugin on three harnesses and couples to easy-cheese at the artifact boundary only.

## Record

- work_id: `tenet-sweep-follow-ups`
- revision: `rev-1c27a4a21499` (revision 4)
- resume: `/cheese --continue tenet-sweep-follow-ups`
