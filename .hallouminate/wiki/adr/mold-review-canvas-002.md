# ADR: Bundle the review server and assets in the mold archive

Status: accepted design (2026-09-16); implementation pending.

## Context

A separate application adds installation and coordination work.

## Decision

Ship the Python server and prebuilt browser resources in the Mold archive.[^1]

## Alternatives

A separately installed web application reduces archive size but adds deployment requirements.

## Consequences

Build-time JavaScript tooling is permitted. Runtime Node, external assets, and asset downloads are excluded.

The user permits spec extraction with browser-test and typed-plan prerequisites still open.
This decision does not waive implementation gates or claim the feature exists.

The prebuilt resources are tracked under `src/easy_cheese/skills/mold/assets/`.
The Vite build is deterministic, so a fresh build on a current `main` changes no file.
A dependency bump can change every chunk and its hashed name.
`just mold-review-assets-check` runs in the `mold-review` CI job and fails until someone commits the rebuild.
Dependabot cannot commit that rebuild, so its npm pull requests need a pushed `just mold-review-build`.
Issue #880 records the drift that #841 caused.

## Related records

- [Domain model](../domain-model.md)
- [Existing-runner gate](./outer-tdd-gates-005.md)
- [Skill Python bundle doctrine](../architecture/skill-python-bundle-doctrine.md)

[^1]: Approved design spec: /Users/paul/.local/share/cheese/paulnsorensen-easy-cheese/specs/mold-review-canvas.md; Decisions and Approved scope audit. User confirms extraction overrides on 2026-09-16.
