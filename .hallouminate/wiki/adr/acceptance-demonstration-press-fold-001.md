# ADR: Cook owns an automatic Press loop with a coverage_gap outcome

Status: accepted (2026-10-14), implemented 2026-10-15

Spec: acceptance-demonstration-press-fold (durable specs corpus).

Supersedes: [adr/outer-tdd-gates-003](./outer-tdd-gates-003.md).

## Context

No phase owned the first acceptance test. Mold Test Contracts were optional, Cook made test-first optional, and Press refused first coverage. Press was also a separate user-selected step after Cook, so a run could skip it. A change could pass every gate while the user's original complaint still occurred.

## Decision

Cook owns first acceptance coverage as a reported obligation, not a RED gate. After its taste test on behavior work, Cook dispatches a fresh-context Press agent. Press acts like a scoped mini taste test: it inspects the acceptance check, asks whether the original complaint can still occur while every test passes, and selects one false-success attack. A `finding` returns to Cook as a correction (two per attack). A new `coverage_gap` outcome returns to Cook to add first coverage; a second `coverage_gap` halts. The fan pathway runs Press per curd; the barrier runs Cook's integrated acceptance check, and no global post-merge Press runs. `/press` stays callable for a manual re-run.

## Consequences

The handoff menus offer no Press option, and Cook emits `next: age | mold | done`. The `cook -> press` registry transition and the fan `NextStep` `press` value leave. Each behavior change costs one extra fresh-context dispatch per round. Commit 0009f3fa's removal of the RED gate stays in force.
