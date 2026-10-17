# ADR: Measure SKILL.md bodies in estimated tokens, not lines

The skill-size gate measures the `SKILL.md` body in estimated tokens against Anthropic's 5k Level-2 budget; line count is reported as a secondary signal only.

## Decision record

### ADR-001: Estimated tokens as the gated unit [status: accepted]

- **Context:** Anthropic publishes two body figures — "under 500 lines" and a Level-2 load budget of "under 5k tokens".[^1] Measured against this repo they disagree sharply. All 16 skills clear 500 lines (max `age` at 385), yet six exceed 5k estimated body tokens (`cook` 9,099, `age` 8,736, `affinage` 7,953, `cheese` 5,543, `mold` 5,357, `cure` 5,130). The divergence is line density: easy-cheese protocol prose runs at a median ~95 bytes/line, against a median of 129 lines across Anthropic's own 17 skills.[^2] A line-based gate would have reported a clean tree while six skills sat over the context budget.
- **Decision:** Gate on estimated tokens of the body only, excluding frontmatter (frontmatter is Level 1 and separately capped at 1024 chars). Estimate as `len(body_bytes) // 4`. Report line count alongside, unenforced.
- **Alternatives:** Gate on lines to match the more prominently published figure; gate on raw bytes; gate on both with either failing.
- **Consequences:** The gate tracks the cost that actually matters — context consumed at Level 2 load — and stays correct as prose density drifts. It diverges from the 500-line number most authors will have read first, so the reason is documented here and in [skill-size-budget](../skill-size-budget.md). Frontmatter-only growth is invisible to this gate by design.

### ADR-001a: The target is 3,600 tokens — this repo's number, not Anthropic's [status: accepted, amends ADR-001]

- **Context:** ADR-001 gated at Anthropic's published Level-2 figure of 5,000 tokens. That collided with `skills/cheese/references/skill-authoring.md`, which had set the repo budget at "roughly 80-150 lines" since PR #138 (`e70d8500`, 2026-06-23). Provenance settled which one yields: the line figure entered as a loosened adaptation of Matt Pocock's \<100-line cap for a third-party skills repo, was never derived from measuring this repo, and had no readers — all three inbound links to that file cite it for the Iron Law template, not the size budget. But its *intent* — stay well inside the platform ceiling — was sound and deliberately chosen, so restating it beat discarding it.
- **Decision:** Convert the existing intent into the gated unit rather than adopt the platform ceiling. At this repo's measured median body density of 95 bytes/line, 150 lines is ~3,560 tokens, so `TARGET_TOKENS = 3600`. Restate `skill-authoring.md` § Size budget in tokens with the same figure, so one number is stated in one place and enforced from it. Error messages attribute 3,600 to this repo, never to Anthropic.
- **Alternatives:** Adopt Anthropic's 5,000 and delete the repo budget; keep both numbers in different units; pick 4,000 for headroom (grandfathers the identical eight skills, so it buys nothing but slack).
- **Consequences:** Eight of 16 skills are over budget and grandfathered, up from six at 5,000. The two tightest compliant skills — `hard-cheese` (3,085) and `plate` (3,078) — hold only ~515 tokens of headroom, so they are effectively frozen too; that is the tighter bar working as intended, not a defect. New skills are held to the repo's standard rather than the platform's ceiling.

Related: [[skill-size-ratchet-002]], [[skill-size-ratchet-003]].

[^1]: https://platform.claude.com/docs/en/agents-and-tools/agent-skills/overview
[^2]: `anthropics/skills` @ `b29e7cf65e5cb78a5ac33d582270551bc74a14eb`, measured 2026-07-24
