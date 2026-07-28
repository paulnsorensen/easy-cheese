# Skill size budget

Measure a `SKILL.md` body in **estimated tokens, not lines**. Lines are a
misleading unit for easy-cheese because our skills carry dense protocol
prose at a median ~95 bytes/line, roughly double the line density of
Anthropic's own skills. Every easy-cheese skill passes the published
500-line rule; six exceed Anthropic's 5k-token ceiling and **eight exceed
this repo's own 3,600-token budget** on the same bodies.

## The published limits

Two are hard (the platform validator rejects the skill); the rest are
recommendations.

| Limit | Value | Kind |
|---|---|---|
| frontmatter `name` | 64 chars | **hard** |
| frontmatter `description` | 1024 chars | **hard** |
| Claude Code listing truncation of `description` + `when_to_use` | 1536 chars | hard in-listing, tunable via `skillListingMaxDescChars` |
| `SKILL.md` body | under 500 lines | recommendation |
| `SKILL.md` body (Level 2 load) | under 5k tokens | recommendation |
| reference nesting depth | one level from `SKILL.md` | recommendation |
| table of contents in a reference file | required above 100 lines | recommendation |
| total bundled content | no practical limit | explicit non-limit |

Sources: [best-practices](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices),
[overview](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/overview),
[code.claude.com/docs/en/skills](https://code.claude.com/docs/en/skills).

The 1024-char `description` cap is the only one currently enforced here
(`.github/scripts/validate_skills.py:38`).

## The three load levels

Anthropic names three, with distinct context costs. The four-directory
skill layout in [architecture](./architecture.md) is the *file shape*;
these are the *load events*, which is what actually costs context.

| Level | What | When it loads | Cost |
|---|---|---|---|
| 1 — Metadata | frontmatter `name` + `description` | always, for every installed skill | ~100 tokens each |
| 2 — Instructions | the `SKILL.md` body | on trigger | target under 5k tokens |
| 3+ — Resources | `references/`, `scripts/`, `assets/` | only on an explicit link from `SKILL.md` | zero until accessed |

Level 3 has **no auto-discovery**. A file the body never links is a file
the model never reads — which makes an orphaned reference dead weight,
not lazy-loaded detail.

## What Anthropic actually ships

Measured on a clone of [`anthropics/skills`](https://github.com/anthropics/skills)
at `b29e7cf65e5cb78a5ac33d582270551bc74a14eb` (2026-07-24): n=17, min 32
lines, **median 129**, max 546 (`claude-api`). Only one skill exceeds
500 lines. `skill-creator` — Anthropic's own authoring skill — sits at
485 and states the rule verbatim at `skills/skill-creator/SKILL.md:86-98`.

Median 129 against a 500 ceiling means the ceiling is a backstop, not a
target.

## Our measurement

16 skills, 2026-07-27, as the gate measures them: body only (frontmatter
excluded), estimated tokens = body bytes ÷ 4. Bold exceeds this repo's
3,600-token budget.

| Skill | lines | ~tokens | ref files |
|---|---|---|---|
| cook | 324 | **9,099** | 4 |
| age | 379 | **8,736** | 9 |
| affinage | 287 | **7,953** | **0** |
| cheese | 173 | **5,543** | 13 |
| mold | 175 | **5,357** | 12 |
| cure | 203 | **5,130** | 2 |
| wheypoint | 231 | **4,570** | 0 |
| pasteurize | 237 | **4,234** | 1 |
| hard-cheese | 196 | 3,085 | 2 |
| plate | 246 | 3,078 | 5 |
| culture | 84 | 2,521 | 0 |
| press | 125 | 2,339 | 1 |
| melt | 166 | 2,178 | 1 |
| briesearch | 87 | 2,064 | 7 |
| easy-cheese-setup | 42 | 760 | 0 |
| ultracook | 17 | 410 | 7 |

Every skill clears 500 lines. Eight exceed the 3,600-token budget; six of
those also exceed Anthropic's 5,000 ceiling. `affinage` is the sharpest
case — ~8k tokens with **zero** reference files, so none of its bulk is
deferrable without new files. The tightest compliant skills,
`hard-cheese` and `plate`, hold only ~515 tokens of headroom.

Two structural findings the line rule cannot see:

- **20 reference files link to other reference files**, violating the
  one-level-deep rule. The documented failure mode is a partial read —
  the model `head`s the first file in a chain and silently misses the
  tail.
- **6 reference files are orphaned** (linked from no `SKILL.md`
  anywhere), and **10 of 16 `SKILL.md` files have no `## References`
  section**, so their reference files carry no stated read-trigger.

Cross-skill linking is legitimate here — `skills/briesearch/SKILL.md`
links `../cheese/references/formatting.md` — so an orphan check must run
**repo-wide**. Scoped per-skill it produces 12 false positives.

## Splitting without routing does not save tokens

Across 55,315 public skills, arXiv 2603.29919 (SkillReducer) finds that
reference files are "loaded in full regardless of task relevance" absent
explicit per-file trigger metadata (Finding F3). The same survey finds
only 38.5% of skill body content is actionable.

The consequence for authoring: moving prose into `references/` buys
nothing unless `SKILL.md` also states *when* to read the file. A bare
split relocates the tokens; it does not defer them.

Caveat — single paper, self-designed benchmark, no independent
replication found. Its descriptive statistics are solid; its causal
claim that compression *improves* quality (+2.8%) is weak evidence.

## Reconciling with the authoring reference

**Resolved 2026-07-27 — the repo budget was restated in tokens, tighter
than the platform ceiling.** The authoring reference (then at
`skills/cheese/references/skill-authoring.md`, since relocated to
`.agents/skills/skill-authoring/SKILL.md` — see
[[cheese-kernel-shared-refs-001]] ADR-001a)
previously set the budget at "roughly 80-150 lines" and argued against a
hard cap. Its provenance decided it: the figure entered in PR #138
(`e70d8500`, 2026-06-23) as a loosened adaptation of Matt Pocock's
\<100-line cap for his own skills repo — never derived from measuring
this repo, and read by nothing (all three inbound links cite that file
for the Iron Law template, not the size budget). An unmeasured, unread,
third-hand number does not outrank measurement.

Converted at this repo's measured median body density of **95 bytes/line**,
150 lines is ~3,560 tokens. The gate therefore targets **3,600 tokens**,
deliberately below Anthropic's 5,000 ceiling, and
`skill-authoring.md` § Size budget now states that figure. 8 of 16 skills
are over it and grandfathered; the tightest compliant skills
(`hard-cheese`, `plate`) hold ~515 tokens of headroom.

> ⚠️ Conflicts with `.agents/skills/skill-authoring/SKILL.md` § Authoring
> review checklist:
> the authoring checklist says references are "one level deep" and then
> that "two levels is the maximum depth" — self-contradictory in its own
> text. Anthropic states one level. The 20 measured violations are only
> violations under the one-level reading. Needs human resolution.

## Enforcement

Gated in CI as a self-tightening ratchet rather than a flat cap, at
`TARGET_TOKENS = 3600` — see [[skill-size-ratchet-001]],
[[skill-size-ratchet-002]], [[skill-size-ratchet-003]].

The budget itself lives in `.agents/skills/skill-authoring/SKILL.md`
§ Size budget, which is the authoring-facing statement of the same number;
this page is the evidence behind it. Baselines are recorded in
`.github/skill-budgets.json` and regenerated only by
`just update-skill-budgets`, which clamps each entry to
`min(measured, prior)` so regeneration can lower a pin but never raise one.

_Source: /briesearch on Agent Skill sizing + direct measurement of anthropics/skills and this repo · Updated: 2026-07-27_
