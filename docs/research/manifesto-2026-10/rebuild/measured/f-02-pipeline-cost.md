# Pipeline cost digest (sub-agent report, 2026-09-21)

Source: 9,022 raw transcripts parsed by the sub-agent (scratch in `/tmp/ec`, not durable), 60 days to 2026-09-21. Claude logs cover 37 days. The parent did not re-run the queries. Cells are p50/p90.

## Full chains (cook AND age AND (cure OR plate), top-level loads)

| harness | n | cook to last phase load, min | active min | tools | fresh input M | output k | cache-read M |
|---|---|---|---|---|---|---|---|
| claude | 7 | 64/220 | 141/309 | 777/1604 | 2.8/5.8 | 394/888 | 84/253 |
| codex | 3 | 35/50 | 72/91 | 377/904 | 1.4/2.7 | 79/224 | 39/88 |
| omp | 24 | 658/2756 | 228/775 | 2536/11004 | 5.3/25.5 | 581/2431 | 170/911 |
| all | 36 | 203/2630 | 163/775 | 1517/10893 | 3.7/25.2 | 443/2395 | 129/897 |

Two "mixed" chains are shared worktree keys and are not one piece of work. 24 of 36 chains are one session on main.

## Baseline, whole tree, sessions that edited code (p50)

- claude, cook loaded: n=16, 448 tools, 50.4M cache-read, 46 edit calls.
- claude, no phase skill: n=46, 82 tools, 9.4M cache-read, 5 edit calls.
- codex, cook loaded: n=18, 372 tools, 16 edit calls.
- codex, no phase skill: n=9, 67 tools, 1 edit call.
- Task size confounds this comparison.

## Rework

- 62 chains with age. 16 (26%) have 2 or more age rounds. The maximum is 13.
- cure loads after the first age in 41 of 62 chains (66%).
- Age rounds before the first plate: p50 1, p90 2.
- 17 of 52 chains plate before any age.
- Reviewer or taste-tester spawns before the first plate: p50 6, p90 28.

## Token share in trees that loaded a phase skill (share of total tokens)

| harness | parent | coder | reviewer + taste | other |
|---|---|---|---|---|
| claude | 59.6 | 21.8 | 12.1 | 6.4 |
| omp | 44.5 | 23.7 | 21.8 | 10.0 |
| codex | 33.3 | 47.4 | 10.9 | 8.4 |

Cache-read is 95% or more of all tokens. A reviewer sub-agent runs 5 to 10 minutes and costs 1M to 4M tokens.

## Caveats

- omp records no branch, so multi-session chains are under-counted.
- codex loads are inferred from SKILL.md reads.
- Rows are whole sessions and overlap across skills.
- No dollar cost was computed.
