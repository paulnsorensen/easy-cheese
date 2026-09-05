# One agent-facing wheypoint verb, with compaction proofs as a sidecar

<certain> `checkpoint` is the only agent-facing write verb; `commit` becomes host-internal, and a compaction proof enters through `checkpoint --compacted <proof.json>`.[^spec]

## ADR-003: `checkpoint --compacted` instead of a public `commit` [status: accepted]

- **Context:** <certain> `checkpoint` refused `compacted`, `compaction`, and `expected_revision_id` as commit-only fields (`src/easy_cheese/skills/wheypoint/checkpoint.py:74,110-120`), so two public verbs overlapped and the SKILL.md had to explain when to use which. No caller outside the wheypoint skill invoked `commit`. The writer-view ADR (workflow-contract-milknado-seam-002) requires agents to write slim views and hosts to fill provenance, so folding `checkpoint` into `commit` was the wrong direction.
- **Decision:** Keep `CheckpointIntent` as the only writer view. Add a `--compacted <proof.json>` flag whose payload is validated as a `CompactionRecord` before the host builds the delta. Remove `commit` from the command list; the function stays as the host-side promotion path.
- **Alternatives:** Keep `commit` public and document it as compaction-only. Rejected: two verbs to teach, and the proof block is a transport detail, not a writer-view field.
- **Consequences:** The proof stays caller-authored, exactly as the compaction docstring argues it must. One verb in the rewritten SKILL.md.
- **Implementation note (2026-09-05):** <certain> Every wheypoint verb, including the new `list`, `log`, and `turns`, keeps the bundle's reply contract of exactly one sorted JSON line. Where the spec's acceptance criteria say "print N lines", the reply carries those lines under a `lines` key (plus typed `items`, `revisions`, or `turns`), so a shell caller pipes the JSON and a human reads `lines`. The compaction proof is part of the request identity: an identical intent submitted with `--compacted` is a new revision, never a replay of the uncompacted one.

## References

[^spec]: `/home/paul/.local/share/cheese/paulnsorensen-easy-cheese/specs/wheypoint-ergonomics.md`, approved 2026-09-05 — fork `F3-compaction`, AC-10.
