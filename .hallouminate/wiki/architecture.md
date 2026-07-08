# Architecture of easy-cheese

easy-cheese is a **skills-only collection**: there is no application
binary, no long-running service, no library to import. Every change adds,
edits, or supports a skill under `skills/<name>/`, following the
[Agent Skills spec](https://agentskills.io/specification). The product
*is* the set of markdown-plus-scripts skills a coding agent loads at
runtime (`AGENTS.md:25`).

## The unit: a skill

A skill is a directory whose shape encodes progressive disclosure
(`README.md:42-53`):

```text
skills/<skill-name>/
├── SKILL.md          # required: YAML frontmatter (name + description) + body
├── references/       # optional: detail pulled in on demand
├── scripts/          # optional: executable helpers (often a .pyz bundle)
└── assets/           # optional: templates / static resources
```

`SKILL.md` is the always-loaded surface. Its frontmatter `description`
is what the host matches against a user request to decide whether to
invoke the skill, so it carries trigger phrases. The body is the
operating procedure; anything heavy is pushed into `references/` and
pulled in only when the flow reaches it. Example: `/mold` keeps its
two-key handshake checklist in `references/handshake.md` and links it
from the body rather than inlining it (`skills/mold/SKILL.md:21`).

## Progressive disclosure

The pattern is deliberate context economy: the agent reads `SKILL.md`
first, then descends into `references/<topic>.md` only for the step it
always-installed `cheese` skill's `references/` directory
(`skills/cheese/references/handoff-gate.md`, `skills/cheese/references/formatting.md`) and
is referenced by sibling-relative path (`../cheese/references/<file>.md`
from a `SKILL.md`, `../../cheese/references/<file>.md` from a
`references/*.md`) (`README.md:53`).

Skills that depend on `shared/scripts/` ship a pre-bundled `.pyz` so the
shared helpers are self-contained at install time — invoked as
`python3 ${CLAUDE_SKILL_DIR}/scripts/<skill>.pyz <subcommand>`
(`skills/mold/SKILL.md:22`). Bundles exist for affinage, briesearch,
cook, melt, mold, and ultracook; `build-pyz.yml` rebuilds them on
every relevant push to `main`.

## The cheese pipeline

The workflow skills compose into one pipeline, ordered
**culture → mold → cook → press → age → cure → ship**
(`skills/mold/SKILL.md:125`, `skills/cook/SKILL.md:90`):

| Skill | Role in the pipeline |
|---|---|
| `/cheese` | Front door — classifies input, routes to the right skill |
| `/culture` | No-write thinking / exploration |
| `/mold` | Converge a fuzzy idea into an approved spec |
| `/cook` | TDD-disciplined implementation of a spec |
| `/press` | Adversarial test hardening |
| `/age` | Ten-dimension review → severity-grouped findings |
| `/cure` | Apply selected findings as focused fixes |
| `/ultracook` | Pipeline a spec in fresh-context isolation; parallel mode fans file-disjoint curds → PRs |

Lower-level **tool skills** sit beneath the pipeline: `/cheez-search`,
`/cheez-read`, `/cheez-write` (tilth-backed primitives), plus the
`/ultracook` composite that chains cook → press → age → cure
non-interactively in fresh-context isolation; its parallel mode (formerly
`/cheese-factory`) fans file-disjoint curds through the `src/fanout/` engine
into reviewable PRs (`AGENTS.md:42-49`).

## Portability is the design center

No repo-wide MCP requirement. Workflow skills *suggest* tools (tilth,
Context7, Tavily, code-review-graph) but carry host-native fallbacks, so
the collection runs on any compliant agent host (`README.md:161`).

The one deliberate exception is the `cheez-*` tool skills: they require
tilth MCP and **hard-fail** when it is unavailable rather than silently
degrade to `grep`/`cat`/`Edit` (`AGENTS.md:73`, `README.md:87`). That
asymmetry is intentional — the workflow skills stay universal; the tool
skills trade portability for AST-grounded precision and announce the
trade by refusing to run without it (`skills/cheez-search/SKILL.md:3-5`).

## Why a wiki at all

Durable architecture/convention/rationale knowledge needs a home that
survives the task that produced it and is worth committing into the tree
— that is this wiki. It is one of three memory lanes: specs and research
reports are durable too but anchor at the out-of-git XDG project corpus,
and transient per-task output stays gitignored under `.cheese/`.
Durability is not the same axis as git-tracking
(`skills/cheese/references/formatting.md:103`); see [wiki-conventions](./wiki-conventions.md)
for the classification rule and
[workflow-invariants](./workflow-invariants.md) for where it sits among
the other pipeline invariants.
