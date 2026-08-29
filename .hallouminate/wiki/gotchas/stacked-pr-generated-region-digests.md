# Stacked PRs must move generated-region digest pins with the edit

`tests/python/test_generated_regions.py` pins SHA-256 digests of
`src/easy_cheese_schemas/_phase_registry_compiler.py` and
`_compiled_phase_registry.py` so those files change only via deliberate
regeneration.

Gotcha (hit in the typing stack, PRs 534–538): the schemas PR edited the
compiler while the digest-constant update rode two PRs later in the stack.
Every intermediate PR failed `just check` standalone — a merge queue would
have broken mid-stack even though the stack tip was green.

Rule: when a stacked PR touches a digest-pinned file, the pinned-constant
update belongs in the SAME commit/PR. Verify each stack branch passes
`just check` independently, not just the tip.

Related: basedpyright per-environment overrides (e.g.
`reportPrivateUsage = "none"` for the `tests` execution environments in
`pyproject.toml`) are the sanctioned scoped alternative to inline
`# pyright: ignore[reportPrivateUsage]` in white-box tests — config change
and comment deletion must also land together, or
`reportUnnecessaryTypeIgnoreComment` fails the gate.
