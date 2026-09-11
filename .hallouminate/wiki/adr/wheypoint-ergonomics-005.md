# Checkpoints must carry the user's words

<certain> A wheypoint checkpoint records user-stated constraints as protected `directive` entries with a verbatim quote, a genesis checkpoint must capture at least one entry or a notes body, and the skill reads the session transcript through a `turns` verb before building the intent.[^spec]

## ADR-005: Typed directives, a genesis capture gate, and transcript-grounded checkpoints [status: accepted]

- **Context:** <certain> On 2026-09-05 the checkpoint for the wheypoint-ergonomics work dropped the user's directives ("is it all in STE100?", "more surviving without sacrificing ability", "without having to literally write an unzip"). The transcript shows why: `EntryKind` had only decision, question, and blocker (`src/easy_cheese_schemas/wheypoint.py:104-108`), so constraints had no typed slot; the installed SKILL.md told the agent to "Reduce unrelated state to a one-line reference" (repo `skills/wheypoint/SKILL.md:30`) and to tailor the document to a focus; and the agent authored the intent from its own evaluation rather than from the user's turns. The user had asked for full-fidelity checkpoints on 2026-08-28, 2026-09-05 01:54, and 2026-09-05 07:01.
- **Decision:** Add `EntryKind.DIRECTIVE` with a `quote` field, stored in a kind-locked `WheypointRecord.directives` ledger and rendered under `## Directives`. Refuse a genesis checkpoint with no entries and no notes. Add a `turns` verb that prints the user's turns from the session transcript (derived from the encoded cwd, with `--session` and `--transcript` overrides) so the skill can require mapping each turn to an entry or a stated omission. Remove the lens's license to drop state; the lens shapes orientation only.
- **Alternatives:** More prose in SKILL.md asking for fidelity. Rejected: #553 shows suggestion-shaped rules are skipped about 99% of the time; only a gate and a typed slot survive.
- **Consequences:** A checkpoint can no longer be a paraphrase with nothing protected. The record grows one ledger. The transcript layout is a host dependency, isolated behind one verb with a loud failure.

## References

[^spec]: `/home/paul/.local/share/cheese/paulnsorensen-easy-cheese/specs/wheypoint-ergonomics.md`, approved 2026-09-05 — fork `loss-fixes`; AC-21, AC-25 to AC-28; `## References` there quotes the nine user turns of session 921cc6a0.
