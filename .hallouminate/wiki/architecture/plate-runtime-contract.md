# Plate runtime contract

Plate owns one Shiv archive with two deterministic helpers; Git, GitHub, and stack mutations remain outside the archive.[^1]

## Commands

- `validate-publication <state.json>` validates terminal evidence at the trust boundary, reports all detected violations, and prints normalized JSON only for a valid state. It enforces mode/topology/provider compatibility, verified artifacts and PRs, a passing quality gate for publication modes, commit SHA shape, and agreement with an optional `pr_plan.plate_layout`.[^2]
- `stack-tools [--cwd <path>]` performs read-only local probes for Graphite, Git Town, and `gh stack`. It distinguishes installation from repository configuration, reports when `gh stack` still needs a remote check, and recommends the first usable provider in Plate's provider order.[^3]

The tool probe never creates stack metadata or invokes provider mutations. Optional executables may be absent because publication validation does not depend on them; this preserves the bundle doctrine's prohibition on required external executables.[^4]

## Skill boundary

Plate prose invokes only `skills/plate/scripts/plate.pyz`. Source lives in `src/easy_cheese/skills/plate/`; the build resolves Plate's complete hash-locked closure ephemerally from the committed external lock, and the checked-in archive is generated deployment output.[^5]

[^1]: skills/plate/SKILL.md:130-141; skills/plate/SKILL.md:238-254
[^2]: src/easy_cheese/skills/plate/publication.py; tests/python/test_plate_runtime.py
[^3]: src/easy_cheese/skills/plate/stack_tools.py; skills/plate/SKILL.md:238-254
[^4]: architecture/skill-python-bundle-doctrine.md:37-49
[^5]: src/easy_cheese/skills/plate/commands.py; requirements/runtime.txt; scripts/build_pyz.py; skills/plate/scripts/plate.pyz

_Source: implemented repository behavior · Updated: 2026-08-28_
