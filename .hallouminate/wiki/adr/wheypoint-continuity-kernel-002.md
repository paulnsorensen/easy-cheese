# Dedicated Wheypoint runtime boundary

<certain> The Wheypoint kernel exposes one dedicated portable runtime while preserving existing shared handoff and path APIs.[^spec]

## ADR-002: Ship a dedicated wheypoint.pyz [status: accepted]

- **Context:** <certain> Before PR #384, main had no Wheypoint bundle, the vendored dependency bundle list named only `ultracook`, and existing consumers called `parse_handoff_slug()` directly.[^code]
- **Decision:** Build `skills/wheypoint/scripts/wheypoint.pyz` with stable JSON `commit`, `resolve`, `show`, and `lint` commands. Stage the private Wheypoint runtime, `easy_cheese_schemas`, and currently vendored attrs/cattrs dependencies into it. Reuse `project_corpus_root()` without changing its semantics.
- **Alternatives:** Create a broader `cheese.pyz` now, or widen the legacy phase-report parser into the continuity authority.
- **Consequences:** `/wheypoint` owns writes, `/cheese --continue` consumes validated results, and the child remains independently dispatchable. A later cross-skill runtime can consume the same public JSON contract rather than reach into private modules.

## Verification gotcha

<certain> Bundle byte verification is interpreter-version-sensitive. A local Python 3.14 rebuild produced identical archive members but different outer bytes, while repository workflows pin Python 3.12.[^python-version] Run bundle reproduction and `just check` with Python 3.12 when the default interpreter differs.

## References

[^spec]: `/home/paul/.local/share/cheese/paulnsorensen-easy-cheese/specs/wheypoint-continuity-kernel.md`, approved 2026-08-02.
[^code]: `scripts/build_pyz.py:83-90,162-175`, `src/wheypoint/wheypoint.py:47-263`, and `shared/scripts/paths.py:223-225`, verified 2026-08-08.

[^python-version]: `.github/workflows/build-pyz.yml:52-55` pins bundle builds to Python 3.12; local `just check` comparison observed 2026-08-02.
