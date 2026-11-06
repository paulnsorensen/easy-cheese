# Rebuild exercise, session 5 (2026-10-03): workflows, the stream, and schema/CLI/living-spec scrutiny

Work id: `rebuild-easy-cheese-from-scratch`. Session: Claude `78e803e4-87f5-5280-9172-6caa905f35e5` in worktree `bridge-cse_017h2fn7qB8PvEMntCMjpBYh`.
No source change. No commit. Three read-only explorer digests fed sections 1-3.
The resume re-pinned two stale links first (rev 5): the schema catalog (#733) and the wiki landscape page (#729 wording fix).

## 1. Schemas (22 registered contracts, 10,656 lines in src/easy_cheese_schemas)

- KEEP (code-produced, many consumers): cook-preparation-result, curd-plan, curd-result, planner-request, planner-result, review-result, mold-cook-handoff, mold-cook-approval, remediation-state, wheypoint-record, wheypoint-revision, work-edge, checkpoint-intent (hand-authored).
- CUT from the runtime catalog: phase-contract (build-time only, generated from skills/*/phase-contract.yaml).
- MERGE candidates (field sets not diffed; speculating): review-request + diagnosis-request; remediation-cure-observation into remediation-state; normalization-receipt into wheypoint-revision; handoff-pointer vs mold-cook-handoff; agent-writer-view as the envelope over five writer views.
- Depends on other forks: pr-plan (agent-written YAML, ultracook only).
- compat.py is 683 lines with one migration (curd-plan 0.9 to 1.0, remove_after 2027-06-01); the adapter part (about 160 lines, compat.py:482-683) has no production caller.
- Register: spec (MoldSpecDocument, contracts.py:3094, validator-only today). artifact-ref (contracts.py:599, 27 production files) belongs to the seam record.
- Do not register yet: eval-result (no model; evals are prose), adr and research-report (path helpers only).
- Unregistered model-shaped classes: ProgressReceipt, ReviewDebt, EvidenceRef, Landing, WheypointDelta, WheypointProjection; fork-taste-verdict and taste-ledger are allowlisted URIs with no model (schema_runtime.py:83-87).
- Nondeterminism enters only where agents author JSON: five writer-view kinds, CheckpointIntent, PrPlan.
- Untyped hops on spec -> curd-plan -> execution -> eval: spec markdown, evidence_keys strings, pr-plan.yaml, evals.
- Net: about 16-18 contracts after cuts and merges, plus spec.

## 2. CLIs (115 verbs across 13 bundles)

- Registry is code: per-skill COMMANDS tuples with @bundle_command (shared/bundle_commands.py:74,91,118); commands.md is generated, so prose and code agree.
- 115 = 110 + 5 wheypoint verbs from #735 (backlinks, fork, link, shape, unlink).
- 15 shared verb names fill 47 entries; each wrapper re-imports shared.*; a nested `cheese <noun> <verb>` collapses 47 to 15 with no logic change.
- Name clash: validate (cook vs wheypoint). Bundle-specific wrapper: age write-handoff-artifact (review lock).
- Judgment classes: 77 deterministic workers, 13 routing helpers, 8 render-only, 17 with no prose reference (9 in the cook fan-out set; verify in-code callers before deleting).
- Position: keep routing logic in code (directive v-6dbfeb3c409b); move ownership and naming to the skill, not the logic into prose. This disagrees with the 09-24 thread direction.
- Packaging: 13 archives, about 40 MB; each duplicates shared/, cli/ and dependencies (about 2.8 MB). mold is 5.7 MB because src/easy_cheese/skills/mold/assets holds 8.2 MB of canvas frontend. One cheese.pyz would be about 3 MB plus assets.

## 3. Living spec today

- Spec sections are heading-named (contracts.py:3023-3040), with no section id; stable ids exist only at line level (AC-n, G-n, F-n).
- Revision rewrites the whole file; no section-patch verb exists.
- The canvas renders from hand-authored JSON (review-canvas.md:15-34), not from the spec; it returns answers, pins {id, anchor, text}, Excalidraw scenes and Mermaid source (review.py:504-523).
- html_report.render is one-way Markdown to HTML with no heading ids (html_report.py:205).
- Reprinting: per-round Mold ledger plus full-spec show before the Cook question (estimate 0.3-1 KB per round, 3-6 KB per show; unmeasured).
- Agent recommendation: typed markdown with stable section ids as the single source; `mold spec patch --section <id> --base <digest>`; canvas renders from sections with pins anchored to section ids; chat prints only deltas.

## 4. Workflows, by example

1. Stream. "Rethink how wheypoint links work." Talk; patch the shape; a two-line reference typo is an inline edit; section edges passes the ready check, is frozen, and goes to cook as a piece in the background; molding continues on section resolve; an edit to edges mid-flight makes the piece return stale and queues a follow-up piece; batch review at the boundary; publish. Variants: think-only (no writes); promotion when a section becomes a public contract.
2. Build. "Add --json to plate status per this spec." Pieces, review, publish. Open: its own workflow, or a stream that starts ready.
3. Review. "Review PR #742." Findings report, optional fixes.
4. Fix a bug. "ground-check cannot resolve citations under .hallouminate/." Reproduction, cause, red-then-green regression test, minimal fix, publish.
5. Land a PR. "#741 has three review comments and failing lint." Triage, fix, reply, green CI.
6. Research. "How do other packs keep a living spec?" Cited, verified, durable answer.

Shared steps: publish, resume, spike, decision record.
Out of core: dead-code hunts, NIH audits, issue triage, the understanding check (optional add-on candidates).

## 5. Provisional support names

| Name | Meaning |
| --- | --- |
| Stream | The iterative session that hosts talk and build together. |
| Shape | The living spec or idea doc; single source, patched in place. |
| Section | A shape unit with a stable id; diagrams link from it. |
| Ledger | Ideas, decisions, info, and open forks. |
| Fork | An open decision that names the sections it touches. |
| Move | One turn's action: talk, inline edit, or piece. |
| Inline edit | A small, low-risk change made in the parent. |
| Inline gate | Code check on risk, size, and context cost; returns inline or piece. |
| Piece | A frozen shape slice that cook builds in its own worktree. |
| Ready check | Passes when no open fork touches the piece's sections or interfaces. |
| Freeze | Pinning a section digest at dispatch. |
| Stale return | A piece that finished against a section that changed after dispatch. |
| Follow-up piece | The queued delta after a stale return. |
| Promotion | Going full mold: the shape gains curds, ADRs, and a validated handoff. |
| Boundary | A piece return, a publish, or the session end. |
| Batch review | One review of the accumulated diff at a boundary. |
| Review debt | Unreviewed stream edits; publish refuses while any remain. |
| Checkpoint | A wheypoint at each boundary. |

## 6. Rules proposed this session (agent recommendations, not decided)

- Inline gate: risk (the closed leverage-trigger list in skills/cheese/references/routing-policy.md) plus size (a few files, tens of lines) plus context cost (wide reading becomes a piece). The agent may upgrade to a piece but never downgrade.
- Promotion line: promote when a cold executor will run the work (more than one dependent piece, parallel workers, another session or person, an RFD) or when a contract others depend on changes (contract, new-slice, cross-slice-dep triggers). Other triggers keep user steering and strong review but not the full document.
- Conflict found: routing-policy.md says any fired leverage trigger routes to full mold; skills/mold/references/tiers.md:19 says a trigger only rules out Quick. The rebuild keeps one rule.
- Concurrent mold and cook: freeze the slice, not the doc; freeze the interface in the piece's section; detect edits to frozen sections by digest (the same mechanism as stale-artifact-link and review publish --base-revision); cap one or two pieces in flight; returns are digests, not diffs.
- Harness dependency: background pieces need sub-agents; omp has none, so the pack's orchestration or milknado runs them there (seam record).

## 7. Open decisions

1. Canvas: feedback only (leaning) or an editing surface.
2. Build: its own workflow, or a stream that starts ready.
3. Promotion line: cold executor or public contract (leaning), or any leverage trigger.
4. Inline line: risk plus size in code (leaning), risk only, or agent judgment.
5. Section edited under an in-flight piece: finish and queue a follow-up (leaning), or cancel and resend.
6. Is the six-workflow list complete; reconcile with the 15 workflows mapped in the 09-24 thread.
