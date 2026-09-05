# Agent-invoked mini-spec mode — full procedure

Read this when `/mold` uses agent-invoked mini-spec mode. This mode is the tier-1 escalation from `/cheese`, per `SKILL.md` § Agent-invoked mini-spec mode. It provides the full procedure, mini-spec schema, and `## Provenance` rules.

1. **Derive slug** from the user's ask (kebab-case noun-phrase, ≤ 4 words).
2. **Write the resolver-owned `<spec-path>`** with the mini-spec schema below. Resolve it via `python3 skills/mold/scripts/mold.pyz artifact-path specs <slug>`. Never hardcode a repo-local spec path: the resolver anchors it at the durable corpus, matching the Curdle step.
3. **Validate the minted spec** with `python3 skills/mold/scripts/mold.pyz validate-spec --strict <spec-path>`. Stop on a nonzero exit; no malformed or legacy-compatible artifact advances to Cook.
4. **Return the resolved spec path** to `/cheese`: every disposition dispatches `/cook --auto <spec-path>`. Return the full resolver path, never a bare slug.
5. **Append `--hard`** to that command when the user passed the flag. Every disposition carries it. Plate alone runs the gate.

The two-key handshake does not fire in this mode. The agent-introduced-scope check still runs implicitly. Every distinguishing noun in the mini-spec must come from the user's input or the tier-2 `/culture` or `/briesearch` synthesis. Record that synthesis in `## Provenance`. Never add any other noun. The mini-spec records only the user's request. It never records the agent's interpretation.

## Mini-spec schema

```markdown
---
slug: <kebab-slug>
status: draft
source: agent-mini-spec
created: <YYYY-MM-DD>
confidence: <low | medium | high>
intent: <one-sentence restatement of the user's ask>
blast_radius: low | medium | high
inputs: <one-line>
outputs: <one-line>
agent_resolution: []
gate_applicability:
  disposition: red-required | not-applicable
  work_class: behavior | docs-only | refactor-only | test-only | appearance-only
  ui_surface: browser | non-browser | not-applicable
  reason: <required only for not-applicable>
verification: <one-line: the obvious check>
---

## Contract
<one paragraph: behavior change, scope boundary>

## Grounding

Add exactly one row for each probe. Record the real outcome. Never invent a row.

| Probe | Outcome | Evidence |
| --- | --- | --- |
| wiki | <hit \| miss \| unavailable> | <wiki path and one-line finding, or what was attempted> |
| explorer | <hit \| miss \| unavailable> | <explorer digest path and one-line finding, or what was attempted> |

## Acceptance
- AC-1: <verifiable check 1>
- AC-2: <verifiable check 2>

## Test Contracts
Include this section only for `red-required`; omit it for `not-applicable`.

| Acceptance ID | Interface referent | Outermost stable seam | Expected failure | Mode | Interface version | Matrix rows |
| --- | --- | --- | --- | --- | --- | --- |
| AC-1 | <public interface> | <existing outer seam> | <expected RED assertion> | tracer | | |
| AC-2 | <public interface> | <existing outer seam> | <expected RED assertion> | contract-matrix | <ratified version> | <row 1><br><row 2> |

## Non-goals
- <what we are NOT changing>

## Provenance (tier 2 only)
- culture: <one-line synthesis of what /culture concluded>
- briesearch: <one-line synthesis>; artifact: research/<slug>/<slug>.md
```

`source: agent-mini-spec` marks the strict Mold production path. New behavior
specs must set `ui_surface` to exactly `browser` or `non-browser`; closed
non-behavior specs, including `appearance-only`, set it to `not-applicable`.
The taste and curd gates reject an omitted or unsupported value. `browser`
requires every Test Contract to name an existing browser/E2E interface and
outer seam; `non-browser` never consults contract prose for classification.
User-invoked ceremony specs use `source: mold-handshake` and the same rules.
Specs without either marker remain legacy-compatible.

`## Provenance` appears only when `/cheese` reaches tier 2 before falling into tier 1. This occurs when `/culture` or `/briesearch` supplies context absent from the original input. Omit the section when tier 1 fires on the raw input.

### Briesearch sidechain contract

Mold owns the dialogue and the approval state for every research request. Apply these rules to each `/briesearch` call:

- Send `invocation: sidechain` in the request. A missing value defaults to `top-level`, which releases the run from Mold's control.
- Send `allow_question: false`. Mold asks every user question itself.
- Reuse the Mold parent slug for the request. Do not derive a second slug. The parent slug also names the research artifact.
- Record the corpus-relative artifact path `research/<slug>/<slug>.md` in the `artifact:` field. Never record an absolute path. This link preserves the citations. It lets `/cook` or any later skill read them again without new research.
- Map a `don't know` result to an open hypothesis. Record no `outcome`. Keep Curdle blocked until new evidence or an explicit `[TBD]` decision settles it.
- Omit `artifact:` only when `/briesearch` reads local code patterns and writes no durable file.
