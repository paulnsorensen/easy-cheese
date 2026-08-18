# ADR: cook joins COMMON_CONSUMERS so its documented common.pyz fallback ships

Status: accepted (2026-08-18)

Spec: pyz-pipeline-contracts (durable specs corpus).

## Context

skills/cook/references/fan-pathway.md:33-35 documents a common.pyz read_handoff_slug fallback, but COMMON_CONSUMERS excluded cook, so bundle-only hosts had no handoff-read path.

## Decision

Add cook to COMMON_CONSUMERS and ship skills/cook/scripts/common.pyz; the contract test additionally asserts any common.pyz prose reference implies consumer membership. Rejected: correcting the doc (documents the hole instead of filling it).

## Consequences

The documented contract is true on bundle-only installs; the failure class is test-enforced.
