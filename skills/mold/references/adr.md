# ADRs — durable design rationale

Mold records only decisions that pass the strict eligibility filter as Architecture
Decision Records (ADRs). The approved spec and its ADRs are **durable** project
records: the spec keeps the implementation contract, while ADRs preserve rationale
that meets all three criteria below. Write them at Curdle, after the two-key
handshake, in phase one's local atomic write.

## What earns an ADR

Write one ADR only when the decision meets **all three** criteria:

1. **Hard to reverse** — changing it later would require a migration, compatibility
   break, broad rewrite, or comparable recovery work.
2. **Surprising without context** — a future reader could not infer why this choice
   was made from the code and spec alone.
3. **Result of a real trade-off** — at least two viable alternatives carried
   materially different costs or benefits.

A forced move with no viable alternative fails the trade-off criterion. An obvious
or easily reversible choice fails even when it was discussed at length. Keep every
non-qualifying decision in the spec's one-line decision-log; do not inflate it into
an ADR.

## Decision ledger

Mold's per-round decision ledger (`Decided / Asking / [AGENT-DECIDED]`, see
`../SKILL.md` § Rules) feeds Curdle's ADR eligibility pass. Each
`[AGENT-DECIDED]` entry is a **candidate**, not an automatic ADR: evaluate it
against all three criteria exactly as a user-made decision. Qualifiers become ADRs;
non-qualifiers remain in the spec's one-line decision-log (`curdle.md` § Spec
template). The ledger keeps no separate file (ADR-004).

## Resolution — where ADRs land (portable, never hardcoded)

Mold runs in arbitrary repos. The corpus is resolved **dynamically at curdle**,
never hardcoded — there is no `easy-cheese:wiki` baked into a runtime path.

```pseudocode
adr_target():
  # 1. Probe for a hallouminate wiki at the CONSUMER's root repo.
  #    Shape-match the corpus, never exact-match a placeholder — the repo name is
  #    dynamic (matches grounding.md and paths.py's domain_model_target()).
  corpus = first(c for c in hallouminate.list_corpora()
                 if c.startswith("repo:") and c.endswith(":wiki"))   # dynamic; their repo, not ours
  if corpus:
    return ("hallouminate", corpus)        # searchable, cross-session
  # 2. Fall back to a tracked file path everywhere else.
  return ("file", "docs/adr/<slug>-NNN.md")  # tracked in the consumer's repo
```

- **hallouminate present:** write each ADR into the consumer's
  `repo:<their-repo>:wiki` corpus via `add_markdown`. The corpus is shape-matched
  from `list_corpora`, never a literal — that is the portability invariant.
- **hallouminate absent:** write `docs/adr/<slug>-NNN.md` (tracked), emit a **loud
  one-line note** that the ADR went to a file rather than the wiki (never a silent
  degrade — see `curdle.md` § Atomic write), and recommend installing hallouminate
  so future rationale becomes searchable.
- **probe shape varies by harness** `[?]`: if `list_corpora` is unreachable, fall
  back to the tracked file path and say so — never block curdle on the probe.

The spec path follows the separate artifact resolver contract and remains in its
durable project corpus; ADR target resolution does not make the approved spec
transient.

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

ADRs are a phase-one Curdle by-product. Write them **after** both handshake keys
pass, in the same local atomic step as the durable spec and before any external
follow-up publication. They never substitute for the spec's own `## Decisions`
line: the ADR is the long form; the Decisions bullet is the index entry.
