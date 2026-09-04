# Cheese to Mold Edge Review

## State

broken

## Contract trace

- Cheese routes fuzzy design work to `/mold` (`skills/cheese/SKILL.md:179-188`).
- Mold accepts direct fuzzy design work and starts its full ceremony (`skills/mold/SKILL.md:10-13`).
- Cheese invokes Mold mini-spec mode after all Cook fast-path checks pass (`skills/cheese/SKILL.md:41-47,64-68`).
- Mold accepts that mode and skips dialogue and the handshake (`skills/mold/SKILL.md:13,45-51`).
- Mold receives the original request and optional Culture or Briesearch synthesis (`skills/mold/references/mini-spec-mode.md:5,10,62`).
- Mold runs `artifact-path specs <slug>` and `validate-spec --strict <spec-path>` (`skills/mold/references/mini-spec-mode.md:5-8`).
- The resolver selects the XDG corpus for durable phases (`src/easy_cheese/shared/paths.py:252-260,263-284`).
- Mold returns the full resolved path, not a bare slug (`skills/mold/references/mini-spec-mode.md:8`).
- Cheese then dispatches `/cook --auto <spec-path>` (`skills/cheese/references/escalation.md:10-16`).
- The validator returns status 1 for a missing or invalid specification (`src/easy_cheese/skills/mold/validate_spec.py:738-769`).
- No Python import connects Cheese and Mold. The edge uses skill dispatch and Markdown contracts only.

## Evidence

| Side | Evidence | Result |
| --- | --- | --- |
| Cheese producer | `skills/cheese/references/escalation.md:10-16` | Cheese dispatches Mold, reads its returned path, and dispatches Cook. |
| Mold consumer | `skills/mold/SKILL.md:13,45-51` | Mold recognizes the Cheese mini-spec mode. |
| Mold producer | `skills/mold/references/mini-spec-mode.md:5-8` | Mold resolves, validates, and returns the full specification path. |
| Cheese consumer | `skills/cheese/SKILL.md:120-122` | Cheese expects a Mold specification pointer for continuation. |
| Mold handoff | `src/easy_cheese/shared/taste_test.py:1141-1153`; `src/easy_cheese/skills/mold/curd_count.py:131-160` | Mold uses `spec_ref`, `command`, `metadata`, and top-level `mode`. |
| Cheese handoff | `skills/cheese/references/continue-resume.md:109-119` | Cheese reads the Mold pointer from `artifact:`. |

## Findings by severity

### Blocker

none

### High

- **Cheese names the wrong output path.** Cheese says Mold writes `.cheese/specs/<slug>.md` (`skills/cheese/references/escalation.md:10-16`). Mold forbids that path and requires its resolver (`skills/mold/references/mini-spec-mode.md:5-8`). The resolver places specifications in the XDG corpus (`src/easy_cheese/shared/paths.py:252-260,263-284`). This stale Cheese contract can create a duplicate specification or bypass the durable corpus. **Fix:** Make Cheese name only the resolver-owned path. Keep the full returned path as the Cook argument.

- **The specification pointer has incompatible carriers.** Mold mini-spec mode returns an unnamed path (`skills/mold/references/mini-spec-mode.md:8`). Mold full mode emits `handoff.spec_ref` (`skills/mold/references/curd-count.md:79-99`). Cheese continuation instead reads the current specification from `artifact:` (`skills/cheese/references/continue-resume.md:115-119`). The handback contract reserves `artifact:` for a prior report (`skills/cheese/references/handback-contract.md:15-32`). It also omits Mold from phase handback producers (`skills/cheese/references/handback-contract.md:83-91`). **Fix:** Add one canonical `spec_ref` field. Register Mold as a producer. Make Cheese read only `spec_ref`. Keep `artifact:` for the prior report.

### Medium

- **Tests do not exercise the edge from both sides.** Cheese tests verify the routing receipt, but they do not consume a Mold result (`tests/python/test_cheese_routing_receipt.py:47-57`). Mold tests verify its path rule and Cook command only (`tests/python/test_mold_followup_routing.py:275-284`; `tests/python/test_curd_count.py:329-335`). No test passes a Mold result through Cheese. **Fix:** Add a Cheese consumer test for this handback. Add a Mold producer test for the same handback. Prove that validation failure prevents Cook dispatch.

### Low

none

## Verification

- `mold.pyz artifact-path specs seam-probe` returned an XDG specification path.
- `mold.pyz validate-spec --strict` accepted the documented mini-spec shape.
- Ten seam-adjacent tests passed. These tests do not cover the cross-skill return path.

## STE100 status

- `skills/cheese/SKILL.md`: compliant for the reviewed edge prose.
- `skills/mold/SKILL.md:12`: not compliant. It uses past tense and passive voice. **Fix:** Use present tense and name Mold as the actor.
