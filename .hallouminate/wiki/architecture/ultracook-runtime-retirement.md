# Ultracook runtime retirement

The `/ultracook` skill remains a redirect stub for muscle-memory invocations, but its published Python runtime is retired. `scripts/runtime_gates.py` discovers Python-backed skills only from `src/easy_cheese/skills/*/commands.py`, and `skills/ultracook/` carries no `wedge.toml`, so no Ultracook archive is built or shipped. Fan-out runtime commands are owned by `/cook`; retained files under `skills/ultracook/references/` are compatibility templates consumed by Cook's fan pathway. This keeps redirect documentation stable while preventing a stale archive from entering releases.[^1]

[^1]: scripts/runtime_gates.py:`SKILLS`; skills/ultracook/SKILL.md:16-21; tests/python/test_wedge_pin.py

_Source: deployment reference correction for [PR #729](https://github.com/paulnsorensen/easy-cheese/pull/729) · Updated: 2026-09-28 · Supersedes: extensionless launcher references from the initial Wedge proposal._
