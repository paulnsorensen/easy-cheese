# ADR: Bundle builds verify the staged import closure, including function-body imports

Status: superseded (2026-09-27)

Wedge replaces the `build_pyz.py`/`check_bundles.py` pipeline this record governed. Archives remain committed under the approved A correction. The generated-runtime and command-surface gates it relied on live on in `scripts/runtime_gates.py`; see [[architecture/pyz-bundling-pipeline]].

Spec: pyz-pipeline-contracts (durable specs corpus).

## Context

Cross-directory imports ride on the hand-maintained EXTRA_MODULES dict; a missing entry ships a bundle that fails only when a lazy (function-body) import executes. The --help smoke test covers module-level imports only.

## Decision

After staging each bundle, build_pyz AST-scans every staged file and requires each absolute import — module-level and function-body — to resolve to stdlib, a staged module, or a vendored dependency; unresolved imports fail the build naming module and importer. Rejected: top-level-only checking (adds nothing over the existing smoke test).

## Consequences

Registry omissions become build failures instead of runtime ImportErrors on rare code paths.

_Source: deployment reference correction for [PR #729](https://github.com/paulnsorensen/easy-cheese/pull/729) · Updated: 2026-09-28 · Supersedes: extensionless launcher references from the initial Wedge proposal._
