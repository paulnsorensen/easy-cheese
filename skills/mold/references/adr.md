# ADRs — durable design rationale

Mold records the non-obvious decisions of a session as Architecture Decision
Records (ADRs). The spec is transient; the ADRs are **durable** — they outlive
the spec and stay searchable cross-session (ADR-002). Write them at curdle, after
the two-key handshake, alongside the spec write.

## What earns an ADR

One ADR per decision a future reader would otherwise have to reverse-engineer:

- a chosen approach over a real alternative (the trade-off, not the obvious pick);
- a constraint discovered mid-dialogue (a Prototype Cycle answer that changed the
  design; a `[CONFLICT]` the codebase forced);
- anything tagged a Decision in the spec that has a substantive rationale.

Do **not** write an ADR for a forced move with no alternative, or for a detail the
spec body already states plainly.

## Decision ledger

Mold's per-round decision ledger (`Decided / Asking / [AGENT-DECIDED]`, see
`../SKILL.md` § Rules) persists **here at curdle**: each `[AGENT-DECIDED]` call
that had a real alternative the user could have vetoed earns an ADR — it is
exactly the kind of decision a future reader would otherwise reverse-engineer.
Minor calls with no surviving alternative ride the spec's one-line decision-log
(`curdle.md` § Spec template) instead of a full ADR; the ledger keeps no separate
file (ADR-004).

## Resolution — where ADRs land (portable, never hardcoded)

Mold runs in arbitrary repos. The corpus is resolved **dynamically at curdle**,
never hardcoded — there is no `easy-cheese:wiki` baked into a runtime path.

```pseudocode
adr_target():
  # 1. Probe for a hallouminate wiki at the CONSUMER's root repo.
  corpus = first(c for c in hallouminate.list_corpora()
                 if c == "repo:<their-repo>:wiki")        # dynamic; their repo, not ours
  if corpus:
    return ("hallouminate", corpus)        # searchable, cross-session
  # 2. Fall back to a tracked file path everywhere else.
  return ("file", "docs/adr/<slug>-NNN.md")  # tracked in the consumer's repo
```

- **hallouminate present:** write each ADR into the consumer's
  `repo:<their-repo>:wiki` corpus via `add_markdown`. The repo name comes from
  `list_corpora`, never a literal — that is the portability invariant.
- **hallouminate absent:** write `docs/adr/<slug>-NNN.md` (tracked), and
  recommend installing hallouminate so future rationale becomes searchable.
- **probe shape varies by harness** `[?]`: if `list_corpora` is unreachable, fall
  back to the tracked file path and say so — never block curdle on the probe.

## ADR format

Mirror the spec's own `## ADRs` section shape (this very spec uses it):

```markdown
### ADR-NNN: <one-line decision title>  [status: accepted]
- **Context:** <what made this a real decision; the forces in play>
- **Decision:** <what we chose>
- **Alternatives:** <the rejected options and why>
- **Consequences:** <what this buys and what it costs later>
```

Numbering is per-slug (`<slug>-001`, `-002`, …) on the file fallback; in the wiki,
prefix the page slug the same way so the series stays grouped.

## Timing

ADRs are a curdle by-product. They are written **after** both handshake keys pass,
in the same atomic step as the spec — never before approval, never as a substitute
for the spec's own `## Decisions` line (the ADR is the long form; the Decisions
bullet is the index entry).
