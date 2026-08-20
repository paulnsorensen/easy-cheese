# ADR: Script locations are published as a generated, gated map plus per-source banners

Status: accepted (2026-08-18)

Spec: pyz-pipeline-contracts (durable specs corpus).

## Context

src/ mixed Astro site and Python sources with no artifact mapping subcommands to source files; the only explainer lived in .agents/skills/python-authoring/SKILL.md.

## Decision

build_pyz compiles src/PYTHON_SCRIPTS.md (bundle, subcommand, source path) from its registries with a byte-match staleness gate mirroring the schema catalog; every registered source opens with a one-line ships-as banner asserted by test; a thin hand-written src/README.md explains and points at the map. Rejected: hand-written docs alone (rot silently).

## Consequences

Where-does-this-live is answered by a generated artifact that cannot drift, at both the directory and the file.
