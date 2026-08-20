# ADR: The subcommand registry is pruned to the prose-referenced set with strict two-way equality

Status: accepted (2026-08-18)

Spec: pyz-pipeline-contracts (durable specs corpus).

## Context

Three registries drifted independently: build_pyz SKILLS, skill markdown, and the hand-copied SKILL_SUBCOMMANDS test dict (already missing 3 entries). 3 registrations were dead (press red-gate, ultracook curd-block, ultracook age-route) and 9 were invoked only by tests.

## Decision

Registry equals prose: the 3 dead registrations are removed, the 9 test-only subcommands are demoted to direct module tests, and tests/python/test_skill_contract.py asserts strict two-way equality derived from build_pyz.SKILLS. The hand copy is deleted. Rejected: internal-flag equality (registry carries two meanings).

## Consequences

The registry means exactly one thing; bundle bloat and doc rot both fail tests.
