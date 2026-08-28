# ADR: Bundle currency remains a dedicated build gate

Status: superseded (2026-08-28)

Spec: pyz-pipeline-contracts (durable specs corpus).

This ADR records an unimplemented local-gate proposal. The implemented Shiv pipeline keeps archive rebuilding and currency comparison in the dedicated bundle workflow rather than adding them to `just check`.[^1]

## Historical context

The CRC currency check ran only in CI, so pull requests could fail after runtime source changed without a corresponding archive rebuild.

## Historical decision

The proposal added `check_bundles.py` to the `just check` dependency chain and added a scoped prek hook for runtime changes.

## Supersession

The current `just check` recipe runs linting, tests, and the documentation build. It does not rebuild archives or run `scripts/check_bundles.py`.[^2] Running the checker without first rebuilding the archives would compare the working-tree archives with their committed versions, not with changed runtime source. The dedicated `build-pyz.yml` workflow installs the pinned build tools, rebuilds the archives, compares canonical archive content with `HEAD`, and runs bundle isolation tests.[^3]

Contributors must run `just bundle` after changes to runtime source, build inputs, phase contracts, locks, or committed archives. Do not describe archive currency as part of `just check` unless the gate first performs an authoritative rebuild.[^4]

[^1]: .hallouminate/wiki/architecture/pyz-bundling-pipeline.md
[^2]: justfile:14-39,74-78
[^3]: .github/workflows/build-pyz.yml:39-78; scripts/check_bundles.py:1-196
[^4]: README.md; CONTRIBUTING.md

_Source: implemented repository behavior · Updated: 2026-08-28 · Supersedes: the unimplemented local `just check` and prek proposal accepted 2026-08-18_
