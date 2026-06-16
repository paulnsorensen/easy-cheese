# pocock-parity — mattpocock/skills inventory

**Source**: <https://github.com/mattpocock/skills>  
**Default branch**: main  
**Fetched**: 2026-06-16  
**Tree raw**: `.cheese/research/pocock-parity/raw/tree.txt`

---

## Complete Skill Inventory

### Active skills — included in plugin.json (the distributed plugin)

| category | skill | one-line purpose | path |
|---|---|---|---|
| engineering | diagnose | Disciplined diagnosis loop for hard bugs and performance regressions: reproduce → minimise → hypothesise → instrument → fix → regression-test | skills/engineering/diagnose/SKILL.md |
| engineering | grill-with-docs | Grilling session that challenges your plan against the existing domain model, sharpens terminology, and updates CONTEXT.md / ADRs inline | skills/engineering/grill-with-docs/SKILL.md |
| engineering | improve-codebase-architecture | Find deepening opportunities in a codebase, informed by domain language in CONTEXT.md and decisions in docs/adr/ | skills/engineering/improve-codebase-architecture/SKILL.md |
| engineering | prototype | Build a throwaway prototype — routes between a runnable terminal app (state/logic questions) or multiple UI variations on one route | skills/engineering/prototype/SKILL.md |
| engineering | setup-matt-pocock-skills | Scaffold per-repo config (issue tracker, triage labels, domain doc layout) that the other engineering skills assume | skills/engineering/setup-matt-pocock-skills/SKILL.md |
| engineering | tdd | TDD with red-green-refactor loop; tests verify behaviour through public interfaces | skills/engineering/tdd/SKILL.md |
| engineering | to-issues | Break a plan/spec/PRD into independently-grabbable issues on the project issue tracker using tracer-bullet vertical slices | skills/engineering/to-issues/SKILL.md |
| engineering | to-prd | Turn the current conversation context into a PRD and publish it to the project issue tracker | skills/engineering/to-prd/SKILL.md |
| engineering | triage | Move issues through a state machine of triage roles (new → ready → in-progress etc.) | skills/engineering/triage/SKILL.md |
| engineering | zoom-out | Tell the agent to zoom out and map all relevant modules and callers at a higher abstraction level | skills/engineering/zoom-out/SKILL.md |
| productivity | caveman | Ultra-compressed ~75% token-reduction communication mode — drops filler, articles, pleasantries | skills/productivity/caveman/SKILL.md |
| productivity | grill-me | Interview the user relentlessly about a plan/design until reaching shared understanding, one question at a time | skills/productivity/grill-me/SKILL.md |
| productivity | handoff | Compact the current conversation into a handoff document for another agent (saves to OS temp dir) | skills/productivity/handoff/SKILL.md |
| productivity | teach | Teach the user a new skill/concept within the workspace, stateful across sessions | skills/productivity/teach/SKILL.md |
| productivity | write-a-skill | Create new agent skills with proper structure, progressive disclosure, and bundled resources | skills/productivity/write-a-skill/SKILL.md |

### Active skills — NOT in plugin.json (present in repo but not distributed via the plugin)

| category | skill | one-line purpose | path |
|---|---|---|---|
| misc | git-guardrails-claude-code | Set up Claude Code PreToolUse hooks to block dangerous git commands (push, reset --hard, clean, branch -D) | skills/misc/git-guardrails-claude-code/SKILL.md |
| misc | migrate-to-shoehorn | Migrate test files from `as` type assertions to @total-typescript/shoehorn | skills/misc/migrate-to-shoehorn/SKILL.md |
| misc | scaffold-exercises | Create exercise directory structures (sections, problems, solutions, explainers) that pass linting | skills/misc/scaffold-exercises/SKILL.md |
| misc | setup-pre-commit | Set up Husky pre-commit hooks with lint-staged (Prettier), type checking, and tests | skills/misc/setup-pre-commit/SKILL.md |
| personal | edit-article | Edit and improve articles by restructuring sections, improving clarity, tightening prose | skills/personal/edit-article/SKILL.md |
| personal | obsidian-vault | Search, create, and manage notes in Obsidian vault with wikilinks and index notes | skills/personal/obsidian-vault/SKILL.md |

### In-progress skills (explicitly labelled unstable)

| category | skill | one-line purpose | path |
|---|---|---|---|
| in-progress | review | Two-axis review (Standards + Spec) of diff since a fixed point, parallel sub-agents | skills/in-progress/review/SKILL.md |
| in-progress | writing-beats | Shape an article as a journey of narrative beats, choose-your-own-adventure style | skills/in-progress/writing-beats/SKILL.md |
| in-progress | writing-fragments | Grilling session that mines user for heterogeneous writing fragments, appends to a raw-material file | skills/in-progress/writing-fragments/SKILL.md |
| in-progress | writing-shape | Take a raw-material file and shape it into a publishable article conversationally | skills/in-progress/writing-shape/SKILL.md |

### Deprecated skills (in skills/deprecated/, explicitly retired)

| category | skill | one-line purpose | path |
|---|---|---|---|
| deprecated | design-an-interface | Generate multiple radically different interface designs for a module via parallel sub-agents | skills/deprecated/design-an-interface/SKILL.md |
| deprecated | qa | Interactive QA session where user reports bugs conversationally and agent files GitHub issues | skills/deprecated/qa/SKILL.md |
| deprecated | request-refactor-plan | Create a detailed refactor plan with tiny commits via user interview, file as GitHub issue | skills/deprecated/request-refactor-plan/SKILL.md |
| deprecated | ubiquitous-language | Extract a DDD-style ubiquitous language glossary, flag ambiguities, save to UBIQUITOUS_LANGUAGE.md | skills/deprecated/ubiquitous-language/SKILL.md |

---

## Web UI / Server / Dashboard

**No.** The repo ships no HTML files, no server, no `package.json` with a web frontend, no `localhost` references, and no dashboard. The only non-skill assets of note are:

- `.claude-plugin/plugin.json` — Claude Code plugin manifest listing the 15 distributed skills
- `scripts/link-skills.sh` and `scripts/list-skills.sh` — shell scripts for local dev linking
- `docs/adr/` — one ADR about setup patterns
- `CONTEXT.md` / `CLAUDE.md` — repo-level context docs

Citation: tree enumeration via `gh api repos/mattpocock/skills/git/trees/main?recursive=1` returned no `.html`, no `package.json`, no `server.*` file. Plugin manifest confirmed via `gh api repos/mattpocock/skills/contents/.claude-plugin/plugin.json`.

---

## Parity mapping to easy-cheese toolkit

Known adaptations already made:
- `diagnose` → our `/pasteurize`
- `handoff` → our `/wheypoint`

Skills with no obvious easy-cheese equivalent (candidates for parity work):
- `grill-with-docs` — domain-model stress-test with CONTEXT.md / ADR updates inline (closest we have: `/duck`, but narrower)
- `improve-codebase-architecture` — structured deepening/refactor discovery informed by domain docs (closest: `/age` for review, but that is not architecture-improvement-focused)
- `prototype` — throwaway prototype scaffold with logic vs UI branch routing (no direct equivalent found)
- `setup-matt-pocock-skills` — per-repo AGENTS.md config scaffold for issue tracker + triage labels (no direct equivalent)
- `tdd` — opinionated TDD loop with interface-first philosophy (our `/tdd-assertions` covers assertion quality; full TDD loop skill is different)
- `to-issues` — plan-to-issues vertical-slice breakdown (no direct equivalent)
- `to-prd` — conversation-to-PRD publisher (no direct equivalent; `/spec` is adjacent)
- `triage` — issue state-machine triage (no direct equivalent; `/affinage` is PR-centric not issue-centric)
- `zoom-out` — zoom-out navigation command (our `/xray` or `/grok-codebase` partially overlap)
- `caveman` — token-reduction communication mode (no direct equivalent)
- `grill-me` — plan stress-test interview (closest: `/duck`)
- `teach` — stateful multi-session teaching (no direct equivalent)
- `write-a-skill` — skill authoring assistant (our `/skill-creator` is the direct equivalent — covered)
- `git-guardrails-claude-code` — git safety hooks (partially: our settings block some git ops, but not via a dedicated skill)
- `review` (in-progress) — Standards + Spec dual-axis review (closest: `/age` + `/affinage` combined, but not this exact shape)

---

## Evidence table

| Claim | Source | Confidence |
|---|---|---|
| Default branch is `main` | `gh repo view mattpocock/skills --json defaultBranchRef` | certain |
| 15 skills distributed via plugin.json | `gh api repos/mattpocock/skills/contents/.claude-plugin/plugin.json` | certain |
| 6 additional skills in misc/ and personal/ not in plugin | tree + individual SKILL.md fetches | certain |
| 4 in-progress skills explicitly labelled unstable | tree + SKILL.md frontmatter reads | certain |
| 4 deprecated skills in skills/deprecated/ | tree + SKILL.md frontmatter reads | certain |
| No HTML, server, web frontend, or localhost references in repo | recursive tree enumeration (116 paths, zero matching those patterns) | certain |
| `diagnose` → `/pasteurize` and `handoff` → `/wheypoint` are known adaptations | caller context | certain |
