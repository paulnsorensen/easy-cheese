# ADR: Bundle builds verify the staged import closure, including function-body imports

Status: accepted (2026-08-18)

Spec: pyz-pipeline-contracts (durable specs corpus).

## Context

Cross-directory imports ride on the hand-maintained EXTRA_MODULES dict; a missing entry ships a bundle that fails only when a lazy (function-body) import executes. The --help smoke test covers module-level imports only.

## Decision

After staging each bundle, build_pyz AST-scans every staged file and requires each absolute import — module-level and function-body — to resolve to stdlib, a staged module, or a vendored dependency; unresolved imports fail the build naming module and importer. Rejected: top-level-only checking (adds nothing over the existing smoke test).

## Consequences

Registry omissions become build failures instead of runtime ImportErrors on rare code paths.
