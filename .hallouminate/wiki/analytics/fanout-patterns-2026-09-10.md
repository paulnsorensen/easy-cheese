# Fan-out patterns — 2026-09-10

Session-analytics pass over the Claude harness, 2026-07-12 → 2026-09-10: 83 sessions with `Agent` spawns, 609 dispatches (coder 240, reviewer 148, explorer 88, researcher 58). Follow-up to [skill-adherence-2026-08-30](./skill-adherence-2026-08-30.md). Filed as comments on #552, #553, #654, #658; labels on #623, #658; paulnsorensen/dotfiles#952 for the agent-definition half. This page records what a future pass would otherwise rederive.

## Findings

1. **There is no parallel fan-out.** 0 same-second bursts across 609 spawns; 22% of spawn-minutes hold 2+ spawns. Every "fan-out" is a serial chain. Isolation cost is paid, wall-clock benefit is not. `age/references/fan-out.md` says one worker per lens but never says "in one message".
2. **Coder chains are continuations, not splits.** 154/240 coder spawns follow another coder; 42 are retry/resume/finish, 27 apply-fix, 33 curd/slice. 18 results are `blocked:`; 11 are `blocked: out of context`, all with a `.cheese/notes/` resume brief. Root cause is thin briefs (#623: Done means 0%, Scope fence 2%), not curd granularity. Each resume is a new worktree (#658).
3. **Age does not over-fan; it absorbs cure.** Per age run: 51 runs spawn 0 reviewers, 73 spawn 1–2, none 3+. But 67 coder spawns occur while `/age` is the active skill (39 cure-shaped by description) vs 32 under `/cure`. Confirms #552 with time-ordered attribution.
4. **Reviewer mode gate never fires.** 72/148 reviewer prompts carry no `Review mode` text; 0 returned the blocked handoff that `reviewer.md` promises. Fourth instance of #553.
5. **Taste-test in one agent is enough; the loop is the cost.** Fix-follow-up rate after taste-test 16% (4/25) vs severity-report 12% (6/51) at equal ~3.2K prompt size. Mold fork taste tests ran 6 rounds on one draft (`b15683d0`) and v7–v9 on another, all at opus/high. Led to the `reviewer (taste-test) | default | medium` rows in `agent-resolution.md` and `routing-policy.md`.
6. **Cheap tiers were already the default.** `~/.claude/agents/`: coder/explorer/researcher `sonnet`, reviewer `opus`, whey-drainer `haiku`. 91% of dispatches pass no `model`, so `inherit` resolves to those. The gap is a missing gate-runner role: whey-drainer spawned once, roquefort-wrecker twice, in 60 days.
7. **Mold spawns no coders.** A session-level join showed 15.4 coders per mold session; time-ordered attribution shows 0. The coders belonged to ultracook (38), age (26), cook (12) later in the same sessions.

## Measurement gotchas (session-analytics DuckDB)

- **Attribute by time, not by session.** Join `agent_spawns` to the most recent prior `skill_invocations` row in the same session (`last_value(... IGNORE NULLS) OVER (PARTITION BY sessionId ORDER BY ts)`). A session-level `JOIN … USING (sessionId)` credits every skill in the session with every spawn and produced the false mold number above.
- **Agent durations are not measurable for background dispatches.** `tool_results.timestamp` for `run_in_background: true` is the spawn acknowledgement, so p50 reads 0.0 min. Only foreground spawns carry a real duration.
- **`inherit` hides the tier.** `json_extract_string(input,'$.model')` is NULL for 91% of Agent calls; the effective model is the agent definition's `model:` frontmatter, which the log does not record. Read `~/.claude/agents/*.md` (or the dotfiles source) alongside the query.
- **Reviewer mode detection.** Match `ILIKE '%taste-test%'` and `ILIKE '%severity-report%'` on the prompt; the 72 "unspecified" prompts contained no `review mode` substring in any form, so this is not a phrasing miss.
- **DuckDB reserved words in aliases:** `name`, `mode`, `types`, `sample` fail to parse as column aliases; use `nm`, `review_mode`, etc.
