# ADR: hard-cheese retained despite local zero-use signal

**Status:** accepted (2026-07-07)

The S6 zero-use audit (`.cheese/skill-improver/2026-07-07-s6-zero-use-verdicts.md`) recommended retiring hard-cheese: its triggers route correctly (90% / 0% FP), but local usage was zero on every channel since launch. The retirement shipped as a commit on PR #243 and was **reverted** the same day.

## Why retained

The audit's traffic data covered only the maintainer's machine. hard-cheese is actively used by external consumers of this library — the population it was built for. Local zero-use is not evidence of zero demand for a published catalog skill.

## Lesson for future audits

Before retiring any skill from the published catalog, demand evidence must cover the consumer population, not just local `sessions.duckdb`. Local telemetry can justify *trigger fixes* (pasteurize, same audit) but not *retirement* of catalog skills. The lighter option — demoting from default install while keeping it in the catalog — should be the ceiling for local-only evidence.
