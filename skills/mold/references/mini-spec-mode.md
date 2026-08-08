# Agent-invoked mini-spec mode — full procedure

Read this when `/mold` is invoked in agent-invoked mini-spec mode (tier-1 escalation from `/cheese`, per `SKILL.md` § Agent-invoked mini-spec mode) — the full procedure, the mini-spec schema, and the `## Provenance` rules.

1. **Derive slug** from the user's ask (kebab-case noun-phrase, ≤ 4 words).
2. **Write the resolver-owned `<spec-path>`** with the mini-spec schema below. Resolve it via `python3 shared/scripts/artifact_path.py specs <slug>`; if you're on a host that only exposes the packaged helper, `python3 skills/mold/scripts/mold.pyz artifact-path specs <slug>` is the fallback. Never hardcode a repo-local spec path: the resolver anchors it at the durable corpus, matching the Curdle step.
3. **Return the resolved spec path** to `/cheese`: `red-required` dispatches `/cut --auto <spec-path>`; closed `not-applicable` dispatches `/cook --auto <spec-path>`. Return the full resolver path, never a bare slug.

The two-key handshake does not fire in this mode. The agent-introduced-scope check still runs implicitly: every distinguishing noun in the mini-spec must come from the user's input or from the tier-2 `/culture` / `/briesearch` synthesis recorded in `## Provenance`. Anything else is a silent agent addition and is forbidden — the mini-spec records only what the user asked for, not what the agent thinks they might have meant.

## Mini-spec schema

```markdown
---
slug: <kebab-slug>
source: agent-mini-spec
intent: <one-sentence restatement of the user's ask>
blast_radius: low | medium | high
inputs: <one-line>
outputs: <one-line>
gate_applicability:
  disposition: red-required | not-applicable
  work_class: behavior | docs-only | refactor-only | test-only | appearance-only
  ui_surface: browser | non-browser | not-applicable
  reason: <required only for not-applicable>
verification: <one-line: the obvious check>
---

## Contract
<one paragraph: behaviour change, scope boundary>

## Acceptance
- AC-1: <verifiable check 1>
- AC-2: <verifiable check 2>

## Test Contracts (red-required only; omit for not-applicable)
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
Specs without either marker remain legacy-compatible for Cut.

`## Provenance` appears only when `/cheese` reached tier 2 before falling into tier 1 — i.e., when `/culture` or `/briesearch` contributed context the original input lacked. Omit the section when tier 1 fires on the raw input. When `/briesearch` ran, the `artifact:` field links the durable cited research at `research/<slug>/<slug>.md` so the citations are preserved and `/cook` (or any later skill) can re-read them without re-researching. Omit `artifact:` only when `/briesearch` answered from local code patterns alone and wrote no durable file.
