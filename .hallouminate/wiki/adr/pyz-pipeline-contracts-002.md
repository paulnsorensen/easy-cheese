# ADR: Bundle currency is enforced locally by just check and a scoped prek hook

Status: accepted (2026-08-18)

Spec: pyz-pipeline-contracts (durable specs corpus).

## Context

The CRC currency check ran only in CI (build-pyz.yml), so PRs recurrently failed 'check .pyz bundles are current' (e.g. PR #424) after src/ edits without just bundle.

## Decision

check_bundles.py joins the just check dependency chain, and a prek bundle-currency hook fires on commits touching src/, shared/, or skills/*/phase-contract.yaml. Rejected: CI auto-commit (bot pushes, rebase noise).

## Consequences

Staleness fails at the gate or the commit, not a CI round-trip later.
