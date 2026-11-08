# Research: What would a from-scratch rebuild of easy-cheese keep, cut, or move into code?

Date: 2026-09-21. Invocation: top-level. Slug: `rebuild-easy-cheese-from-scratch`.

## Assumptions in the question

- The question assumes that most practitioners still use a two-step spec-then-ship workflow. The evidence supports this for published packs. No survey measures practitioner behavior.
- The question assumes that easy-cheese output is more robust than the output of other packs. No source compares output quality. This report gives no evidence for or against it.
- The question assumes that easy-cheese is slow. Session logs support this.

## Routing

```text
ROUTING DECISION:
- Library/API documentation:        YES (provider: vendor docs through Tavily extract and native web fetch)
- Current-web discovery/extraction: YES (provider: Tavily; freshness: 2025-09 to 2026-09-21)
- Repository knowledge/wiki:        YES (provider: Hallouminate)
- Local code intelligence:          YES (provider: tilth, git, session-analytics transcripts)
- Git hosting/examples:             YES (provider: native web fetch of repository pages)
SOURCE PRIORITY: checkout code and session logs for local behavior; wiki for rationale; vendor docs for harness features
```

All five capabilities ran. The packaging pass (prefix `c`) ran discovery only. Its claims are committed-but-skipped for page content and carry `speculating`.

```yaml
agent_resolution:
  work: fetch and synthesize one heavy source
  selected: researcher (5 spawns), explorer (4 spawns), general-purpose (2 spawns)
  permissions: read-only, fresh context
  fallback_used: explorer replaced one researcher that ended twice without a report
```

## Finding

The local evidence shows a small used core and a large unused surface. Four skills (`age`, `cook`, `plate`, `cure`) carry most sessions. About 30 listed skills have four or fewer loads in 60 days. The repo ships 17,578 prose lines and 52,249 source lines. The project's own prune audit confirms 157 bloat findings and rejects none. One subsystem (fan-out, remediation, checkpoint, review lock: about 5,200 source lines) absorbs repeated feature and fix commits. The wiki records that each mechanism fixed a real failure. The wiki also records that 51 of 83 measured `/age` sessions ran zero reviewers.

The pipeline is slow in measured terms. A full cook-to-plate chain has a p50 of 3.4 hours from cook to the last phase load and 2.7 hours of active time. It uses about 1,500 tool calls and 129M cache-read tokens. Cache-read tokens are 95% or more of all tokens. Parent context growth is the largest single cost. Sub-agents take 40% to 67% of tokens.

External evidence supports the code-over-prose philosophy with measured savings from Anthropic. It also shows that harnesses now supply plan mode, review, PR follow-up, and compaction natively, except Pi, which omits sub-agents and plan mode. Most easy-cheese loads come from omp, a Pi fork. Every surveyed pack runs a spec-then-implement flow. Most surveyed packs are prose. No surveyed pack publishes a shared schema catalog or a separate adversarial-test phase. The spec-first workflow is contested in primary commentary. Anthropic states that harness assumptions go stale as models improve.

## Evidence

### Local (repo code, git, session logs, wiki)

| Claim | Evidence | Source type | Freshness | Confidence | Caveat |
| --- | --- | --- | --- | --- | --- |
| The repo ships 17,578 prose lines in 31 live skills. `age` has 3,217 lines and `cheese` has 2,270. | `skills/age/SKILL.md:1`, `skills/cheese/SKILL.md:1`; `wc -l` over each SKILL.md, its references, and `.agents/skills` | repo code | 2026-09-21 | `certain` | None |
| Source is 52,249 lines and tests are 76,977 lines. Schemas are 10,308 lines with `contracts.py` as the hub. | `src/easy_cheese_schemas/`, `scripts/build_pyz.py:41-120` | repo code | 2026-09-21 | `certain` | The dependent count of about 92 came from a partial scan. |
| The fan-out, remediation, checkpoint, and review-lock stack is about 5,200 source lines. | `src/easy_cheese/shared/fanout/run_fan.py:1` (1,138), `src/easy_cheese/shared/fanout/remediation.py:1` (469), `src/easy_cheese/shared/wheypoint/checkpoint.py:1` (388), `src/easy_cheese/shared/wheypoint/recovery.py:1` (339), `src/easy_cheese/skills/age/review_lock.py:1` (650), plus `shared/workflow.py` (2,235 as reported) | repo code | 2026-09-21 | `certain` | The parent counted the first five files with `wc -l`. The `workflow.py` count is a sub-agent report. |
| The same resume logic received PRs #710, #708, #706, #701, #387, #384, #382, and #351. | `src/easy_cheese/shared/fanout/remediation.py:1`; `git log --since="6 months ago"` | repo code | 2026-09-21 | `certain` | The reading that each PR adds state without simplification is an agent judgment. |
| Skill use in distinct sessions: `age` 968, `cook` 525, `plate` 131, `cure` 124, `briesearch` 122, `cheese` 88, `affinage` 76, `mold` 69, `press` 64, `pasteurize` 56, `wheypoint` 44, `melt` 43, `culture` 27, `hard-cheese` 1, `easy-cheese-setup` 0. | `raw/f-01-session-usage.md` | session logs | 2026-09-21 | `certain` | omp and Codex counts are skill reads. Claude logs start 2026-08-15. |
| About 85% of skill loads come from omp. | `raw/f-01-session-usage.md` | session logs | 2026-09-21 | `certain` | None |
| `de-slop` has 454 sessions. It was not found under `skills/` in this checkout. | `raw/f-01-session-usage.md` | session logs | 2026-09-21 | `certain` | None |
| Reviewer and coder are about 80% of sub-agent spawns. | `raw/f-01-session-usage.md` | session logs | 2026-09-21 | `certain` | None |
| A full chain (cook and age and cure-or-plate, n=36) has p50 3.4 h cook-to-last-load, 2.7 h active, about 1,500 tool calls, 3.7M fresh input tokens, 0.44M output tokens, and 129M cache-read tokens. The p90 is about 7 times higher. | `raw/f-02-pipeline-cost.md` | session logs | 2026-09-21 | `certain` | omp has 24 of 36 chains. Claude has 7 chains at about 1 h. Codex has 3 chains at about 35 min. |
| Cache-read tokens are 95% or more of all tokens. Sub-agents take 40% to 67%. Reviewers take 11% to 22%. | `raw/f-02-pipeline-cost.md` | session logs | 2026-09-21 | `certain` | No dollar cost was computed. |
| 26% of chains run `age` again. 66% go from `age` to `cure`. The p50 is one review round and 6 reviewer spawns before `plate`. 17 of 52 chains plate before any `age`. | `raw/f-02-pipeline-cost.md` | session logs | 2026-09-21 | `certain` | omp records no branch, so multi-session chains are under-counted. |
| Sessions with `cook` use 4 to 16 times more edit calls than sessions with no phase skill. | `raw/f-02-pipeline-cost.md` | session logs | 2026-09-21 | `certain` | Task size confounds this comparison. It is not pipeline overhead. |
| The prune audit holds 157 "confirm" findings, 39 "soften", and 0 rejected across 18 skills. | `.cheese/skill-prune/actionable.json` | repo code | 2026-09-21 | `certain` | Per-skill detail was not read for every skill. |
| `skills/ultracook/` is a redirect that still ships 681 reference lines. `cut` and RED-gate left in commit `681820f0` (#560). | `skills/ultracook/SKILL.md:3-23`, `git log --diff-filter=D` | repo code | 2026-09-21 | `certain` | None |
| Fan-out sizing is deterministic because LLM classification moved 4 of 30 commits by one tier. | `raw/f-03-wiki-decisions.md` (wiki page adr/deterministic-fanout-sizing-003, lines 23-60) | repository knowledge | 2026-09-21 | `certain` | None |
| The schema catalog is a published contract. A consolidation audit found zero safe root-contract merges. | `raw/f-03-wiki-decisions.md` (wiki pages adr/artifact-schema-validator-compatibility-001, lines 1-20, and architecture/schema-similarity-and-consolidation-audit, lines 394-409) | repository knowledge | 2026-09-21 | `certain` | None |
| 51 of 83 measured `/age` sessions ran zero reviewers. | `raw/f-03-wiki-decisions.md` (wiki page research/review-fanout-policy-comparison, lines 107-123) | repository knowledge | 2026-09-21 | `certain` | None |
| Checkpoint work fixed an unsafe writer-exhaustion resume. The review lock came from four security findings. | `raw/f-03-wiki-decisions.md` (wiki pages gotchas/wheypoint-resume-traps, lines 32-67, and gotchas/age-review-lock-invariants, lines 1-11) | repository knowledge | 2026-09-21 | `certain` | None |
| Multi-harness support is one shared reference and one test. An ADR rejects per-harness duplication. | `skills/cheese/references/harness-portability.md:1`; `raw/f-03-wiki-decisions.md` (wiki page adr/codex-omp-portability-001, lines 1-25) | repo code | 2026-09-21 | `certain` | None |
| The wiki page on RED-gate environment traps is stale. `red_gate` was not found in `src/` or in any `skills/*/SKILL.md`. | `raw/f-03-wiki-decisions.md` (wiki page red-gate-environment-gotchas, lines 23-25); `git grep -i red_gate` over both scopes returned 0 lines | repo code | 2026-09-21 | `speculating` | Five wiki pages still mention RED-gate. |

### External

| Claim | Evidence | Source type | Freshness | Confidence | Caveat |
| --- | --- | --- | --- | --- | --- |
| Skills load in levels. Metadata always loads. The body loads on trigger. Linked files load on demand. Bundled scripts run without entering context. | "the amount of context that can be bundled into a skill is effectively unbounded"[^s1] | vendor blog | 2026-09-21 | `certain` | Authoritative for the format. |
| Code execution over MCP cut one workflow from 150,000 to 2,000 tokens. | "a time and cost saving of 98.7%"[^s2] | vendor blog | 2026-09-21 | `speculating` | One workflow, one vendor. |
| Tool search cut about 77K tokens to 8.7K and raised accuracy. Programmatic tool calling cut tokens 37%. | "This represents an 85% reduction in token usage"[^s3] | vendor blog | 2026-09-21 | `speculating` | Single source. |
| Recall declines as context grows, across models. Smarter models need less prescriptive engineering. | "smarter models require less prescriptive engineering"[^s4] | vendor blog | 2026-09-21 | `speculating` | The Chroma study fetch failed. Thresholds are unverified. |
| Agents use about 4 times the tokens of chat. Multi-agent systems use about 15 times. Most coding tasks have few parallel parts. | "most coding tasks involve fewer truly parallelizable tasks than research"[^s5] | vendor blog | 2026-09-21 | `speculating` | Measured on research tasks. |
| Cache hits cost a fraction of base input. The default cache lifetime is 5 minutes. | "The cache's default minimum lifetime (TTL) is 5 minutes"[^s6] | vendor docs | 2026-09-21 | `certain` | Authoritative for pricing mechanics. |
| Harness assumptions go stale as models improve. | "harnesses encode assumptions about what Claude can't do on its own"[^s7] | vendor blog | 2026-09-21 | `speculating` | Single source. |
| Claude Code ships `/code-review` with `--fix`, `--comment`, and `--post`. | "Requires Claude Code v2.1.227 or later"[^s8] | vendor docs | 2026-09-21 | `certain` | Authoritative for the feature. |
| Cursor loads skills from `.cursor/skills/`, `.claude/skills/`, and `.codex/skills/`. | "Cursor also loads skills from Claude and Codex directories"[^s9] | vendor docs | 2026-09-21 | `certain` | Authoritative for Cursor. |
| Copilot code review reads agent skills, `AGENTS.md`, and `CLAUDE.md` from the PR head branch since 2026-07-17. | "Custom instructions are now read from the head branch"[^s10] | vendor changelog | 2026-09-21 | `certain` | Authoritative for Copilot. |
| Pi omits sub-agents and plan mode. omp discovers skills from other harness directories. | `raw/a-08-pi-ohmypi.md` | discovery only | 2026-09-21 | `speculating` | The pages were not extracted. |
| Codex CLI has native skills, hooks, and a plugin marketplace. | `raw/a-05-codex-changelog.md` | discovery only | 2026-09-21 | `speculating` | The source is a changelog aggregator. |
| SKILL.md portability across harnesses is disputed. | `raw/a-09-skillmd-portability.md` | discovery only | 2026-09-21 | `don't know` | Two blogs disagree. No primary specification was fetched. |
| Every surveyed pack runs a spec-then-implement flow: superpowers, spec-kit, OpenSpec, BMAD, GSD, Pocock skills, the Claude Code `feature-dev` plugin, and Kiro. | Repository and docs pages[^s11][^s12][^s13][^s14][^s15][^s16][^s17][^s18] | Git host and vendor docs | 2026-09-21 | `certain` | This shows pack design, not practitioner behavior. |
| superpowers is prose only. spec-kit ships a Python CLI. OpenSpec ships an npm CLI. GSD ships a Node CLI and hooks. | Repository pages[^s11][^s12][^s13][^s15] | Git host | 2026-09-21 | `certain` | None |
| No surveyed pack publishes a shared schema catalog or a separate adversarial-test phase. | not found in the ten fetched pack pages[^s11][^s12][^s13][^s14][^s15][^s16][^s17][^s18][^s19][^s20] | Git host | 2026-09-21 | `speculating` | Only README and docs landing pages were read. |
| The official `code-review` plugin runs parallel agents with confidence scoring. | Plugin README[^s17] | Git host | 2026-09-21 | `certain` | Claude Code only. |
| The GSD repository is archived. | Repository banner[^s15] | Git host | 2026-09-21 | `certain` | The reason comes from secondary news only. |
| Agents ignore spec instructions in large contexts. Spec markdown is harder to review than code. | "I'd rather review code than all these markdown files"[^s21] | engineering blog | 2026-09-21 | `speculating` | One author, published 2025-10-15. |
| Opus 4.5 has a 50% time horizon of about 320 minutes. Doubling time since 2024 is about 89 days. | Time Horizon 1.1 table[^s22] | research organisation | 2026-09-21 | `speculating` | Wide confidence intervals. |
| Refactoring moves fell from 21% to 3.8%. Duplication rose 81%. Churn rose 15%. | 623M-line analysis[^s23] | vendor research | 2026-09-21 | `speculating` | Single vendor study. |
| Review is the delivery bottleneck. AI review comments have low action rates. | `raw/e-05-search-digests.md` | discovery only | 2026-09-21 | `don't know` | Two cited studies disagree. Neither was opened. |
| `zipapp` needs Python on the target and bundles no dependencies. PEP 723 scripts run under `uv`. Static binaries start faster. | `raw/c-01-tavily.md`, `raw/c-02-tavily.md` | discovery only | 2026-09-21 | `speculating` | No page was extracted in this pass. |

## Open questions

- Which harness is the design target: omp and Pi, or Claude Code? Native features differ between them. `speculating`
- Does the rebuild keep fan-out for implementation? Anthropic reports a 15 times token multiplier and a poor fit for coding. The wiki records a measured sizing policy. `speculating`
- Does the rebuild keep a separate spec phase, a lighter plan artifact, or the harness plan mode? Sources describe all three. `speculating`
- Does `de-slop` belong in the pack? It is the third most loaded skill and is not in the repo. `speculating`
- Does the pyz stay the delivery vehicle, or does a `uv` script, a static binary, or an MCP server replace it? The packaging evidence is discovery only. `speculating`
- Which rejected simplifications in `/home/paul/Dev/easy-cheese/.hallouminate/wiki/skill-parity-analysis.md` still hold? This report did not read that page in full. `speculating`
- Is easy-cheese output more robust than the output of other packs? No source measures this. `don't know`

## Confidence

`speculating` — Local measurements are `certain`. External claims about practitioner workflow, review bottlenecks, and packaging rest on single sources or discovery only.

## Next step

Run `/culture` on the open questions, then `/mold` for the rebuild scope. Read `/home/paul/Dev/easy-cheese/.hallouminate/wiki/skill-parity-analysis.md` first.

## Searched, empty

- Current web via Tavily: "agent skill pack over-engineering criticism minimal skills trend 2026" returned no direct source.
- Current web via Tavily: BMAD and superpowers speed or ceremony complaints returned no pack-specific thread.
- Current web via Tavily: no survey measures the share of teams that use spec-then-implement.
- Current web via Tavily: no same-task comparison of a single-pass agent against a gated pipeline.
- Tavily extract of the Chroma context-rot report failed on output size.
- Hallouminate: no wiki page on the `cheez-*` wrapper retirement or on `pocock-parity` within 10 calls.

## Verification log

- 46 searches, 24 extracts, 5 researcher spawns. See `manifest.json`.
- 23 extracts succeeded. Each maps to one file under `raw/`. One extract failed and supports no claim.
- Raw files with prefix `c` and the files `a-05`, `a-08`, `a-09`, `e-05` hold search digests, not page bodies. Claims from them carry no remote citation.

## References

[^s1]: https://www.anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills (fetched 2026-09-21), `raw/b-01-anthropic-agent-skills.md`.
[^s2]: https://www.anthropic.com/engineering/code-execution-with-mcp (fetched 2026-09-21), `raw/b-02-anthropic-code-execution-mcp.md`.
[^s3]: https://www.anthropic.com/engineering/advanced-tool-use (fetched 2026-09-21), `raw/b-03-anthropic-advanced-tool-use.md`.
[^s4]: https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents (fetched 2026-09-21), `raw/b-04-anthropic-context-engineering.md`.
[^s5]: https://www.anthropic.com/engineering/multi-agent-research-system (fetched 2026-09-21), `raw/b-07-anthropic-multiagent-research-system.md`.
[^s6]: https://platform.claude.com/docs/en/build-with-claude/prompt-caching (fetched 2026-09-21), `raw/b-08-platform-claude-prompt-caching.md`.
[^s7]: https://www.anthropic.com/engineering/managed-agents (fetched 2026-09-21), `raw/e-02-anthropic.com.md`.
[^s8]: https://code.claude.com/docs/en/code-review (fetched 2026-09-21), `raw/a-04-claude-cloud-pr.md`.
[^s9]: https://cursor.com/docs/skills (fetched 2026-09-21), `raw/a-06-cursor.md`.
[^s10]: https://github.blog/changelog/2026-07-17-copilot-code-review-customization-and-configurability-improvements (fetched 2026-09-21), `raw/a-07-copilot.md`.
[^s11]: https://github.com/obra/superpowers (fetched 2026-09-21), `raw/d-01-github-obra-superpowers.md`.
[^s12]: https://github.com/github/spec-kit (fetched 2026-09-21), `raw/d-02-github-spec-kit.md`.
[^s13]: https://github.com/Fission-AI/OpenSpec (fetched 2026-09-21), `raw/d-03-github-openspec.md`.
[^s14]: https://github.com/bmad-code-org/BMAD-METHOD (fetched 2026-09-21), `raw/d-04-github-bmad-method.md`.
[^s15]: https://github.com/gsd-build/get-shit-done (fetched 2026-09-21), `raw/d-07-search-gsd.md`.
[^s16]: https://github.com/mattpocock/skills (fetched 2026-09-21), `raw/d-08-github-mattpocock-skills.md`.
[^s17]: https://github.com/anthropics/claude-code/blob/main/plugins/README.md (fetched 2026-09-21), `raw/d-09-github-claude-code-plugins.md`.
[^s18]: https://kiro.dev/docs/specs/ (fetched 2026-09-21), `raw/d-10-kiro-docs-specs.md`.
[^s19]: https://github.com/buildermethods/agent-os (fetched 2026-09-21), `raw/d-05-github-agent-os.md`.
[^s20]: https://github.com/anthropics/skills (fetched 2026-09-21), `raw/d-06-github-anthropics-skills.md`.
[^s21]: https://martinfowler.com/articles/exploring-gen-ai/sdd-3-tools.html (fetched 2026-09-21), `raw/e-04-martinfowler.com.md`.
[^s22]: https://metr.org/blog/2026-1-29-time-horizon-1-1 (fetched 2026-09-21), `raw/e-01-metr.org.md`.
[^s23]: https://www.gitclear.com/the_ai_code_quality_maintainability_gap (fetched 2026-09-21), `raw/e-03-gitclear.com.md`.
