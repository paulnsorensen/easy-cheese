# Skill adherence analysis — 2026-08-30

Cross-harness session-analytics pass over 1,017 Claude + 385 Codex sessions (Jul 29 – Aug 30 Claude; May 30 – Aug 30 Codex). Filed as #542–#553 comments, #552 (age inline-fix), #553 (umbrella: suggestions → gates). This page records the durable findings and the measurement gotchas so the next pass does not rederive them.

## Core finding

Claude follows skill instructions written as rules and skips instructions written as numbered steps with a degrade clause. Measured adherence to hedged steps is ~1%: 8 `ground` calls in ~350 skill runs; 0 `tilth_deps` in cook/cut/cure/mold/culture; 2 of 62 cooks preceded by a cut; `/age` → `/cure` invoked 9 of 151 times (110 `coder` spawns inside age spans instead). Rules phrased imperatively (mold full ceremony, user-owned forks, press → age) are followed every run. Fix shape is a precondition on the next artifact, not prose (#553).

Codex, reading the same SKILL.md files, grounds (26 calls / 32 mold runs) and delegates (46 spawns) — it re-reads SKILL.md 1–2× per run, Claude gets it injected once.

## Per-skill numbers (Claude, span = invocation → next Skill invocation, idle capped at 10 min)

| skill | n | med active min (p90) | note |
|---|---|---|---|
| cut | 6 | 47 (83) | 3× cook; all red-gate rejections environmental (coverage outputs, virtualenv symlink, digest drift) |
| mold | 20 | 42 (52) | ~10 AskUserQuestions/run, 19-min median wait each → 249 min session wall; 28 Bash/run vs 1 explorer |
| cook | 21 | 15 (27) | healthy |
| cure | 10 | 16 (34) | healthy; budget overruns live in age (88) not cure (9) |
| age | 151 | 9 (46) | 7+-agent runs: 73 min, 32 writes — cure work wearing age's name |
| plate | 37 | 7 (68) | errors are tool call-shape under a 306+493-line prompt |
| press | 6 | 4 (8) | clean on both harnesses |
| wheypoint | 19 | 4 (18) | 35% `commit` rejection since 08-16 — delta schema undocumented (#423) |
| briesearch | 50 | 3 (36) | dedup target is reads/fetches (69/79 tilth_read, 28/30 WebFetch repeats), not searches (9/254) |
| culture | 3 | 12 (20) | short; skipped grounding/deps (#462) |

Codex runs every phase skill 2–4× cheaper (mold 10, cook 5, age 2, cut 21 min).

Artifact I/O confirms write-only types: `.cheese/press` 10 writes / 2 reads, `cure` 24/3, `affinage` 20/3, `cut` 22/5; only `age` (28/96) and `notes` (186/96) are read-heavy.

## Measurement gotchas (session-analytics DB)

- **Codex skill attribution** = `tool_uses.input LIKE '%skills/<x>/SKILL.md%'` (tilth_read / exec_command reads), deduped within 10 min. There is no Skill tool; `$skill` text regex finds nothing because codex user prompts are not ingested at all (all 8,528 codex `user` rows are tool_results).
- **Codex `exec` inputs are encrypted** (`{raw: gAAAA…}`); only `exec_command` (~2.1k calls) is cleartext. 35–81% of codex tool calls per skill are opaque.
- **`exec_command` results do not join** to their `tool_use_id` (output arrives via later `wait`/`write_stdin`), so codex CLI outcomes (red-gate, wheypoint commit) are not attributable.
- `tool_results.is_error_explicit` is documented in canonical-schema.md but absent from the live DB.
- Session wall time is useless for skill cost — use spans and cap idle gaps. Sidechain entries overlap in time, so summing capped gaps at session level overcounts.
- The Bash `.env` guard matches the literal substring in heredoc bodies (including `.venv`); write "virtualenv"/"dotenv" in issue text. `c` is a shell alias — don't name a function `c`.
