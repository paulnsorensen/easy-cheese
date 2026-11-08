# Session usage digest (sub-agent report, 2026-09-21)

Source: session-analytics DuckDB at `~/.claude/skills/session-analytics`. Numbers are as the sub-agent reported them. The parent did not re-run the queries.
Coverage: 5957 omp sessions from 2026-06-30, 2956 claude sessions from 2026-08-15, 439 codex sessions from 2026-05-30.
Count unit: distinct sessions. claude = Skill tool calls, omp = `read skill://X`, codex = reads of the installed SKILL.md.

| skill | omp | codex | claude | all | 60d |
|---|--:|--:|--:|--:|--:|
| age | 822 | 90 | 56 | 968 | 807 |
| cook | 481 | 35 | 9 | 525 | 475 |
| plate | 79 | 14 | 38 | 131 | 122 |
| cure | 85 | 18 | 21 | 124 | 94 |
| briesearch | 92 | 18 | 12 | 122 | 99 |
| cheese | 78 | 8 | 2 | 88 | 51 |
| affinage | 53 | 14 | 9 | 76 | 52 |
| mold | 42 | 16 | 11 | 69 | 58 |
| press | 53 | 6 | 5 | 64 | 54 |
| pasteurize | 47 | 7 | 2 | 56 | 54 |
| wheypoint | 25 | 9 | 10 | 44 | 30 |
| melt | 31 | 9 | 3 | 43 | 35 |
| culture | 23 | 3 | 1 | 27 | 25 |
| ultracook (retired) | 7 | 1 | 0 | 8 | 5 |
| hard-cheese | 1 | 0 | 0 | 1 | 1 |
| easy-cheese-setup | 0 | 0 | 0 | 0 | 0 |

Non-repo skills: de-slop 454, python-authoring 273, tdd-assertions 264, commit 245, bash-shortening 98, gh 91, cheez-read 91, cheez-write 76, cheez-search 74, cut 32.

Typed claude slash commands: briesearch 36, affinage 19, cheese 9, cook 5, plate 3, wheypoint 3.

Sub-agent spawns (claude / omp / codex): reviewer 335 / 720 (+111 cheese-reviewer) / 93; coder 395 / 418 / 88; explorer 87 / 22 (+186 scout) / 57; researcher 35 / 32 / 16; generalist 13 / 19 / 10; taste-tester 15 / 16 / 10; roquefort-wrecker 5 / 19 / 0; whey-drainer 6 / 5 / 0; duckdb-expert 3 / 2 / 8; ghostbuster 3 / 1 / 0; nih-scanner 1 / 0 / 0.

Skills with 1 to 4 sessions: rennet, git-risk, serena-config, claude-local, grilling, domain-modeling, tui-design, grok-codebase, release, routine-scaffold, justfile, xray, worktree-find, ghostbuster, chezmoi, wiki-roadmap.

No recorded loads: gh-bootstrap, oss-hygiene, ci-optimize, build-optimize, safe-settings, prek, copilot, coderabbit, test-sandbox, tui-demo, tui-verify, term-theme, routine-env, ralphify-spec, sliced-bread-audit, triage-sweep, worktree-triage.
