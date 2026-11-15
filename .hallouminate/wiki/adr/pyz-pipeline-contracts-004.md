# ADR: The subcommand registry is pruned to the prose-referenced set with strict two-way equality

Status: superseded (2026-09-27)

Wedge replaces the `build_pyz.py`/`check_bundles.py` pipeline this record governed. Archives remain committed under the approved A correction. The generated-runtime and command-surface gates it relied on live on in `scripts/runtime_gates.py`; see [[architecture/pyz-bundling-pipeline]].

Spec: pyz-pipeline-contracts (durable specs corpus).

## Context

Three registries drifted independently: build_pyz SKILLS, skill markdown, and the hand-copied SKILL_SUBCOMMANDS test dict (already missing 3 entries). 3 registrations were dead (press red-gate, ultracook curd-block, ultracook age-route) and 9 were invoked only by tests.

## Decision

Registry equals prose: the 3 dead registrations are removed, the 9 test-only subcommands are demoted to direct module tests, and tests/python/test_skill_contract.py asserts strict two-way equality derived from build_pyz.SKILLS. The hand copy is deleted. Rejected: internal-flag equality (registry carries two meanings).

## Consequences

The registry means exactly one thing; bundle bloat and doc rot both fail tests.

_Source: deployment reference correction for [PR #729](https://github.com/paulnsorensen/easy-cheese/pull/729) · Updated: 2026-09-28 · Supersedes: extensionless launcher references from the initial Wedge proposal._
