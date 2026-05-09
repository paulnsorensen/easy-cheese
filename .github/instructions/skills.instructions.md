---
applyTo: "skills/**/SKILL.md"
---

# SKILL.md review checklist

Review `SKILL.md` changes the way `/skill-creator` would. The validator
already checks that `name` matches the directory and that frontmatter parses.
Spend your review budget on the things linters cannot see.

## Frontmatter

- `name` matches the parent directory (validator catches mismatch).
- `description` is **the** triggering mechanism. It must:
  - Say what the skill does **and** when to invoke it.
  - Include realistic user phrases ("review this diff", "fix the conflicts",
    "shape this into a spec"), not abstract noun phrases ("code review
    operations").
  - Lean *slightly* pushy. Skills under-trigger by default. A description
    like "Use even when the user says 'tighten things up' before review" is
    fine.
  - Call out boundaries — what this skill does **not** do — when there's a
    sibling skill it could be confused with (e.g., `/age` finds vs `/cure`
    fixes; `/cheez-search` searches vs `/cheez-read` reads).
- `model`, `allowed-tools`, `license` are optional but should be consistent
  across siblings unless a skill genuinely needs different values.

## Body length and progressive disclosure

- Aim for `SKILL.md` under ~500 lines. Going over is fine when justified, but
  if instructions repeat themselves, pull them into `references/<topic>.md`
  and link from `SKILL.md` with a one-line "read this when …" pointer.
- For skills that span multiple variants (per-language fixers, per-conflict
  cascade stages, per-stake findings flows), keep the selection logic in
  `SKILL.md` and put the variant-specific detail in `references/`. Claude
  only loads what it needs.
- Tables of contents only earn their place in reference files >300 lines.

## Bundled resources must pay rent

- Every file under `scripts/`, `references/`, `assets/` has at least one
  reference from `SKILL.md` saying when to use it.
- Scripts encode deterministic, repeated work — if every invocation of the
  skill would re-derive the same shell incantation, bundle it.
- Templates and static text live in `assets/`, not inlined in `SKILL.md`.

## Writing style

- Imperative voice ("Run `/cheez-search`", not "You should run
  `/cheez-search`").
- Explain *why* a step matters when the reasoning isn't self-evident.
  Heavy-handed `MUST` / `ALWAYS` / `NEVER` is a yellow flag — replace with
  reasoning where possible. Reserve all-caps for genuine footguns
  ("**NEVER `git push --force` to `main`**").
- Examples use the `Input → Output` pattern when demonstrating
  transformations. Concrete commands beat abstract descriptions.
- Don't overfit instructions to the examples in the skill. If the rule only
  works for the three commands shown, it won't survive contact with real
  users.

## Scope discipline (this repo specifically)

- Workflow skills (`mold`, `cook`, `press`, `age`, `cure`, `melt`, etc.)
  cover one phase of the lifecycle each. Adding a second phase is a new
  skill, not a new section.
- Tool skills (`cheez-*`) wrap one tilth-MCP capability each. Don't fold
  search and read into the same skill — the chain depends on them being
  independently invokable.
- Only the `cheez-*` skills require an MCP server (tilth). Every other skill
  must degrade cleanly to host-native tools when MCPs are unavailable; do
  not introduce new mandatory-MCP dependencies in workflow skills.
- Skills do not invoke other skills programmatically. Documented handoffs
  (e.g., `/age` → `/cure`, `/cook` → `/press` → `/age`) belong in the
  README's "Suggested flow" or as explicit user-visible prompts in the
  skill body — never as silent auto-dispatch.
- No intent classification, no automatic routing inside a skill body except
  in `/cheese`, where routing **is** the skill's purpose and dispatch is
  gated behind `AskUserQuestion`.

## Quick triage prompt for review comments

For each non-trivial change in the diff, ask:

1. **Trigger test** — would a real user phrasing actually pull this skill in?
2. **Skip test** — could the same outcome land without this paragraph /
   script / reference file? If yes, suggest dropping it.
3. **Generalize test** — does this advice survive when the user's repo
   doesn't look like the example?
4. **Surprise test** — would invoking this skill do anything the description
   didn't promise?

If a comment doesn't trace back to one of those four tests, it probably
belongs in a separate cleanup PR or in CI, not in this review.
