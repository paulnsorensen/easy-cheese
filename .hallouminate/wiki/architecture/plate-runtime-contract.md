# Plate runtime contract

Plate owns one wedge-built archive of deterministic helpers; Git, GitHub, and stack mutations remain outside the archive.[^1] `references/commands.md` lists every command; this page covers the publication helpers.

## Commands

- `validate-publication <state.json>` validates terminal evidence at the trust boundary, reports all detected violations, and prints normalized JSON only for a valid state. It enforces mode/topology/provider compatibility, verified artifacts and PRs, a passing quality gate for publication modes, commit SHA shape, and agreement with an optional `pr_plan`. Provider `ordinary` with topology `stacked` is valid only for an `orthogonal_flat` plan. With `landing` and `pr_plan` both present, the shapes must match unless a `single` collapse carries a non-empty `deviation`.[^2]
- `check-pr-body --body-file <path> [--template-file <path>] [--stack-layer]` lints a drafted PR body before `gh pr create` or `gh pr edit`. It enforces the 40 non-blank-line cap, the required headings (template headings when given), the `Plated as <shape>: <reason>` line, and the filler-word ban. With `--stack-layer` it also requires a stacked shape, a `Stack: <n> of <total>` line, and a mermaid flowchart. Judgment rules (the 20-line small-change cap, claims, reading order) stay in prose.[^6]
- `carve-flat --source-branch <branch> [--pr-plan <path>]` emits, per `orthogonal_flat` group, the `git switch -c` and `git cherry-pick` commands plus a `restore` command. It reuses `easy_cheese.shared.fanout.pr_plan_to_branches.emit_carve_commands`, the same module behind Cook's `pr-plan-to-branches`, and emits no push or PR command.[^7]
- `stack-tools [--cwd <path>]` performs read-only local probes for Graphite, Git Town, and `gh stack`. It distinguishes installation from repository configuration, reports when `gh stack` still needs a remote check, and recommends the first usable provider in Plate's provider order.[^3]

The tool probe never creates stack metadata or invokes provider mutations. Optional executables may be absent because publication validation does not depend on them; this preserves the bundle doctrine's prohibition on required external executables.[^4]

## Skill boundary

Plate prose invokes only `skills/plate/scripts/plate.pyz`. Source lives in `src/easy_cheese/skills/plate/`; the build resolves Plate's complete hash-locked closure ephemerally from the committed external lock, and the checked-in archive is generated deployment output.[^5]

[^1]: skills/plate/SKILL.md:130-141; skills/plate/SKILL.md:238-254
[^2]: src/easy_cheese/skills/plate/publication.py; tests/python/test_plate_runtime.py
[^3]: src/easy_cheese/skills/plate/stack_tools.py; skills/plate/SKILL.md:238-254
[^4]: architecture/skill-python-bundle-doctrine.md:37-49
[^5]: src/easy_cheese/skills/plate/commands.py; uv.lock; skills/plate/wedge.toml; skills/plate/scripts/plate.pyz
[^6]: src/easy_cheese/skills/plate/pr_body.py; tests/python/test_plate_pr_body.py; skills/plate/references/ordinary-pr.md § Body contract
[^7]: src/easy_cheese/skills/plate/flat_carve.py; src/easy_cheese/shared/fanout/pr_plan_to_branches.py; skills/plate/references/ordinary-pr.md § Independent PRs

_Source: implemented repository behavior · Updated: 2026-08-28_

_Source: deployment reference correction for [PR #729](https://github.com/paulnsorensen/easy-cheese/pull/729) · Updated: 2026-09-28 · Supersedes: extensionless launcher references from the initial Wedge proposal._
