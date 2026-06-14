# Skill Authoring — easy-cheese conventions

This document codifies the skill-authoring rules for easy-cheese, drawn from
obra/superpowers (CSO principle, Iron Law template, pressure-test gate) and
Matt Pocock's skills repo (size budget, authoring checklist). It is the
canonical reference for anyone adding or revising a skill.

---

## Description rule (CSO)

The description is the **only thing the harness shows the model when choosing
a skill**. Optimize it for triggering, not explanation.

**The rule:** sentence 1 = capability; sentence 2 = "Use when [triggering
conditions]". No workflow summary, no pipeline-position prose, no feature list.

Rationale: a description that summarizes the skill's workflow creates a
shortcut the model takes *instead of reading the SKILL.md body*. The skill
then silently degrades to its own one-line description.

**Constraints:**
- Maximum 1024 characters (Codex rejects longer descriptions).
- Third-person, present tense.
- Triggering conditions name concrete phrases the user might say.

**Test:** strip the description and ask: could a model choose *this* skill over
all others based on these words alone? If not, the triggers are missing.

---

## Size budget

Keep SKILL.md bodies lean. The goal is a body a model can read in one pass
without losing the thread — not a hard line count.

**Practical budget:**
- A SKILL.md body that fits on one screen (roughly 80-150 lines) stays
  readable. Bodies beyond that almost always have prose that belongs in a
  `references/` file instead.
- Push satellite detail — step-by-step sub-protocols, reference tables,
  prompt templates, large examples — into named `references/*.md` files.
  The SKILL.md body points to them; it does not duplicate them.
- The `references/` dir is the right home for: long rationalization tables,
  output format templates, detailed sub-protocol steps, graph conventions.

**Smell test:** if the SKILL.md body has grown to the point where the Flow
section is buried below a long Inputs section and three flag tables, it is
time to factor.

Note: Matt Pocock's skills repo enforces a hard \<100-line cap. easy-cheese
skills carry more protocol prose by design (the `references/` progressive-
disclosure model), so a hard cap is not appropriate here. The spirit of the
budget — push detail out, keep the body scannable — applies.

---

## Iron Law / Red Flags / Rationalization-table template

Discipline skills (skills that enforce a process, not just explain a
technique) follow this three-part structure. Apply it in a
`## Discipline` section in the SKILL.md body, or in a
`references/<skill>-discipline.md` satellite file when the body is already
at budget.

### Iron Law

One sentence. States the gate that must never be skipped. The Iron Law is
descriptive, not aspirational: it names what the skill *will* refuse to do
without.

Example shape:

> **Iron Law:** No [output] without [prerequisite step] first.

### Red Flags

A short list of signals that the Iron Law is about to be violated. These are
the observable pre-rationalizations — the moment before a step gets skipped.

Example shape:

> **Red Flags** — stop if you notice these:
> - "The tests will obviously pass after this change."
> - "I'll add the test in the next commit."
> - [skill-specific patterns]

### Rationalization table

A table enumerating the excuses an agent uses to skip the Iron Law step, with
an explicit rebuttal for each. The table is adversarial by design: it assumes
the model will reach for a rationalization under pressure.

| Rationalization | Why it fails | Required action |
| --- | --- | --- |
| "The change is obvious, tests would just mirror the code." | A test that mirrors code catches regressions; that is its job. | Write the test. |
| [skill-specific row] | [rebuttal] | [required action] |

Keep the table to the rationalizations actually observed in practice (5-10
rows maximum). An exhaustive list defeats the purpose.

---

## Authoring review checklist

Before a skill ships, verify:

- [ ] **Triggers present.** The description names concrete phrases the user
  might say (not capability prose).
- [ ] **No time-sensitive information.** Skill bodies must not embed version
  numbers, dated pricing, or API endpoints that will rot. Point to docs
  instead.
- [ ] **Concrete examples.** At least one worked example exists — either
  inline or in a `references/` file.
- [ ] **References one level deep.** The SKILL.md body points to
  `references/*.md` files; those files do not point further into their own
  sub-references. Two levels is the maximum depth.
- [ ] **Discipline skills have the Iron Law section.** Any skill that enforces
  a gate or a loop carries the three-part template above.
- [ ] **Dual-listed.** The skill's directory appears in `.claude-plugin/
  plugin.json` `skills` array. The CI check `tests/python/
  test_plugin_manifest.py::test_claude_plugin_manifest_matches_top_level_skills`
  enforces this.

---

## Pressure-test-first authoring gate

**Iron Law: no skill ships without a failing-baseline subagent run first.**

Before writing a new skill body:

1. Construct a representative pressure scenario — a prompt that describes a
   task the skill is meant to improve.
2. Run a subagent on that scenario *without* the skill active. Capture the
   output as the baseline.
3. Identify the specific failure: what did the subagent do wrong, skip, or
   misframe?
4. Write the skill body to address that specific failure.
5. Re-run the subagent with the skill active and confirm the failure is
   corrected.

A skill whose body was never tested against a failing baseline may fix a
problem the model does not actually have, or it may describe a workflow the
model already follows without being told.

---

## `disable-model-invocation` frontmatter (candidate — not yet applied)

Matt Pocock's skills repo uses `disable-model-invocation: true` in the
frontmatter of pure-prompt skills (skills that execute immediately without
re-prompting the model). The Claude Code frontmatter validator (`validate_
skills.py`) already allows this key.

**Status:** candidate-pending-harness-verification. Do not apply to any
easy-cheese skill until the harness behavior is confirmed: what does the
harness do when this key is set, and does it match the intended
"execute immediately" semantics? Document the verification result here
before applying.
