# ADR: curdle wiki writes enforced by gate node + read-back verify, not a Stop-hook

**Status:** accepted (2026-07-14)

mold writes ADRs and the domain-model merge at curdle via prose instruction only
(`skills/mold/references/curdle.md:119-163`, `adr.md`). Nothing gates the write, verifies
it landed, or records it — so a context-heavy curdle silently skips it, and the
hallouminate-absent fallback to files is silent too. The question was how to make an
end-of-dialogue MCP write actually reliable in a prose-driven skill.

## Decision

Enforce with a three-part stack: a **terminal gate node** (`durable-writes-verified`) added
to mold's gate model and the handshake coherence checklist — kept in lockstep by the
existing test (`handshake.md:33`) so it can't be dropped from the skill; a **write → read-back
verify** step (re-read the wiki page via `ground`/`read_markdown`, or re-read the file) that
turns "I claimed I wrote" into "I observed the bytes"; and a **completion record** printed in
curdle output naming each target + backend, so a skip is visible to the author.

## Alternatives

- **Prose-only (status quo)** — rejected: this is exactly the unreliable state being fixed.
- **Stop/SubagentStop hook that greps for a completion marker** — rejected for now: it would
  fire deterministically, but it is harness-specific (Claude vs Codex vs opencode) and
  brittle. Flagged as a possible v2, not built.
- **Post-curdle terminal `durable-writes-verified` node** — rejected *during implementation*
  (this was the constraint that settled Option A over B): mold's lockstep test enforces only
  `kind="gate"` nodes against the handshake checklist, so a terminal node would carry no
  lockstep protection — defeating the enforcement this ADR exists to add. Reframing the gate
  as a pre-handshake *commitment* (`durable-writes`) fits the existing four-artifact lockstep
  (`gate-graph.py` / `handshake.md` / `mold.dot` / `mold.pyz`) with no test-structure change.

## Consequences

Buys: the write is gated (test-enforced in the skill prose), self-caught (read-back), and
visible (completion record) — the reliability ceiling achievable without a runtime hook.
Costs: prose still cannot *force* the agent to act at turn-end; the read-back verify is the
part that actually moves reliability, and a truly deterministic guarantee would still need
the rejected Stop-hook.
