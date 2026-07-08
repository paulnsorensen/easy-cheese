# Skill-parity analysis

Durable record of the one-time analysis that compared easy-cheese's skills
against two external skill collections — and, more importantly, the record of
which proposed changes were **ruled out and why**, so they are not
re-litigated. The actionable findings are tracked as GitHub issues
(#151–#164); the description-format slice shipped in PR #138. This page keeps
the reasoning that does not fit an issue: the falsified claims and the
distinctive leads with no benchmark match.

## Sources & baseline

- **obra/superpowers** — commit `6fd4507`, v5.1.0.
- **mattpocock/skills** — commit `694fa30` (2026-06-10).
- All easy-cheese claims are baselined against the **18-skill manifest**
  (`.claude-plugin/plugin.json`), not an author's ambient `~/.claude` session.
- The full reconciled analysis lived in transient scratch
  (`.cheese/research/easy-cheese-gap-analysis.md`, gitignored); this page is
  its durable distillation.

## What shipped / what's tracked

- **Format slice → PR #138**: CSO descriptions, the Iron Law / Red Flags /
  Rationalization-table template, the authoring checklist, and the
  pressure-test gate (`skills/cheese/references/skill-authoring.md`), plus cook/cure discipline
  reference docs.
- **Open follow-ups → issues #151–#164**: mold glossary durability (#151),
  extend rationalization tables (#152), verification-before-completion (#153),
  sub-agent status vocab + per-task model (#154), curd-prompt stale-path fix
  (#155), issue-intake skill (#156), wheypoint focus arg (#157), and the
  low-severity set (#158–#164).

## Struck — claims falsified against the source

A critique pass falsified these against the cited source. **Do not re-open
without re-checking the cited lines** — each was wrong or overstated when
measured against the actual repo, not merely deprioritized.

- "mold batches questions / lacks one-question cadence" — **false**;
  `skills/mold/references/modes.md:46` mandates one question at a time.
- "mold has no live terminology resolution" — **false**; `modes.md:26`
  resolves and logs terms live (the real gap is *durability*, tracked in #151).
- "mold does not name the code-vs-intent contradiction hunt" — **false**;
  `modes.md:70` defines `[CONFLICT <id>]`.
- "cook has no watch-it-fail proof" — **overstated**; observed-red is a
  required Cut-report item (`skills/cook/references/tdd-loop.md:13`).
- "add a general anti-sycophancy layer" — **redundant**;
  `skills/age/references/voice.md` already covers steelman /
  do-not-manufacture-counterpoints.
- Worktree provenance / isolation recommendations — **wrong repo**; worktree /
  worktree-sweep are not easy-cheese skills. (The parallel-mode fan-out that
  once cited `/worktree-sweep` as a host equivalent now lives in `/ultracook`
  parallel mode, formerly `/cheese-factory`.)
- "caveman-style mid-dialogue compression for mold" — **low value**; at odds
  with mold's disambiguation purpose.

## easy-cheese leads — distinctive, no benchmark match

Strengths the benchmarks lack; preserve rather than "fix": the gate-prose-sync
test; the agent-introduced-scope audit; the hard-fail-over-silent-degrade
invariant; dual-transport orchestration (`cook --auto` vs `ultracook`); melt
squash-residue detection; the runtime context-budget mechanic; durable ADRs to
a dynamically-probed hallouminate corpus; the per-phase handoff-slug system;
the hard-cheese SOLO epistemic-debt gate; the ten-dimension age review engine.

## Provenance

Distilled from `docs/skill-parity-followups.md`, which PR #138 removed in favor
of issues (#151–#164) for actionable items and this page for the durable
reasoning. Introduced via PR #138 rather than the usual post-merge wiki cadence
because it replaces that removed doc in the same change; the `index.md` link
row is refreshed on merge to `main`.
