## Handoff slug

```
status: gated: pick one of three dispositions for the two dangling /cheese-factory references in merged skills
next: cure
mode: single
artifact: none
session: claude:c7095726-5d1c-41e9-8231-73090851148c
git: paulnsorensen/cheese-factory-refs@0fa5e58a
created: 2026-07-28T03:33:11Z
baseline: none
Investigation complete, no edits made: /cook and routing-policy recommend a /cheese-factory that this repo does not ship, because the PR that would have shipped it (#314) is still open.
```

## Document

### Goal

Decide what to do about two merged, behavioural references to `/cheese-factory` in easy-cheese skills, given that the PR which would have made them valid is unmerged and assumed dead.

### State

Investigation is done. Nothing has been edited, committed, or pushed. The working tree is clean at `paulnsorensen/cheese-factory-refs@0fa5e58a`.

**The two live references** (these instruct the agent, they are not comments):

- `skills/cook/SKILL.md:55` — "Above 2 waves, recommend `/cheese-factory` verbatim: 'Recommend cheese-factory above 2 waves; user picks at the gate.'"
- `skills/cheese/references/routing-policy.md:16` — the cook-gate row, same recommendation.

Both landed in `086c970d feat(cook): own the fan-out implementation pathway (#316)`.

**Why they are dangling.** They were forward references to a sibling in the same 4-PR stack. `#315` (routing foundations), `#316` (cook owns the fan pathway), and `#317` (`/ultracook` retired to a redirect) all merged. `#314`, which adds the workflow-only `age-fanout.js` and `cheese-factory.js` pipelines, is still open. `<certain>` There is no `skills/cheese-factory/` in this repo; the only `cheese-factory` artifact on the machine is `~/.claude/workflows/cheese-factory.js`, a personal global Workflow script outside any repo.

**Remaining references are historical and harmless:** `scripts/build_pyz.py:76` (a "formerly" comment), `tests/fanout/python/test_mode.py:100-102` (a passing guard asserting the string is absent from mode source), `tests/python/test_ultracook_skills.py:1211,1213,1421`, `tests/python/test_curd_count.py:265,273`, and three `.hallouminate/wiki/` pages.

### Key decisions and constraints

- **The design record exists, but in dotfiles, not here.** `<certain>` `/Users/paul/Dev/dotfiles/.hallouminate/wiki/adr/cheese-factory-workflow.md` carries ADR-001 through ADR-009 — the full rationale for `/cheese-factory` as a dotfiles Workflow script, born in dotfiles PRs #486 and #494. easy-cheese PR #314 was importing that work, not originating it.
- **Both specs those ADRs cite are absent from this machine.** `<certain>` `specs/cheese-factory-workflow.md` (cited at `adr/cheese-factory-workflow.md:3`) is not in `~/.local/share/cheese/paulnsorensen-dotfiles/specs/`; that directory holds six files and it is not among them. `subagent-routing-overhaul.md` (cited at `skills/cheese/references/routing-policy.md:5` and `.hallouminate/wiki/architecture/age-fanout-router.md:50`) is in none of the seven durable corpora, and `find ~ -name "subagent-routing-overhaul*"` returns zero hits. A second machine was searched by hand and came back empty.
- **`routing-policy.md` declares itself non-authoritative for a page that does not exist.** `<certain>` Line 3 says it mirrors `architecture/subagent-routing-policy.md` in `repo:dotfiles:wiki` "once that page exists". The dotfiles wiki `architecture/` directory contains `subagent-turn-budgets.md` and no `subagent-routing-policy.md`. The in-repo mirror is therefore the only copy of a policy it disclaims ownership of.
- **`/cook` can already run more than two waves.** `<certain>` `src/fanout/curd_block.py:41` sets `MAX_WAVE_SIZE = 4`, which caps slugs *per wave*; `_wave_errors` at `:79-90` validates nothing about the number of waves. The ">2 waves" line is a cost preference, not a capability boundary.
- **easy-cheese implements the review shape dotfiles ADR-006 rejected.** `<certain>` ADR-006 moved review from per-curd to an Integrate barrier plus one whole-diff age, explicitly rejecting "keep per-curd age + add a second barrier age" for double review cost. easy-cheese does exactly that: `.hallouminate/wiki/architecture/ultracook-agent-topology.md:21-24` runs `coder(cook) → coder(press) → reviewer(age) → coder(cure) → reviewer(final age)` per curd, and `skills/cook/SKILL.md:129` adds a post-merge integration pass with its own age. So `/cook` is not missing coverage by pointing at `/cheese-factory` — it is paying N opus reviewers more for it, and the pointer reads like a cost escape hatch that was never labelled as one.

### Decision dossier

**Fork: what to do with the two `/cheese-factory` references, assuming #314 never merges.**

Prior leaning from the session: option 1 now, option 2 filed as an issue. Not confirmed by the user.

*Option 1 — delete the pointer.* Remove the recommendation from `skills/cook/SKILL.md:55` and `skills/cheese/references/routing-policy.md:16`; `/cook` owns every wave count. Breaks nothing: no wave-count cap exists (`src/fanout/curd_block.py:79-90`). Cost stays at the double-review shape. The repo stops advertising something it does not ship.

*Option 2 — delete the pointer and port ADR-006.* Collapse per-curd age into an Integrate barrier and keep the post-merge whole-diff age as the single review, matching the dotfiles workflow. Saves N−1 opus dispatches. Breaks the phase-chain invariants currently enforced in `src/fanout/phase_decision.py` and `src/fanout/validate_manifest.py`, and contradicts `ultracook-agent-topology.md:21-26`, which states that a non-terminal age cannot skip cure and final review. `<speculative>` on effort — `phase_decision.py`'s ordering constraints were not read this session.

*Option 3 — keep it, relabel host-local.* Reword to "if you have the `cheese-factory` workflow installed, above 2 waves is cheaper." Truthful for this machine, noise for every other user of the skill collection.

Independent of the fork, two citation repairs are outstanding: the `routing-policy.md:3` "once that page exists" provenance, and the missing `subagent-routing-overhaul.md`, which is the parent spec of the entire #314–#317 stack.

### Open questions and blockers

- Which of the three options to take. Nothing proceeds until this is picked.
- Whether `#314` is genuinely dead or merely stalled. The session assumed dead per the user's framing; this was not verified against any close decision.
- Whether `subagent-routing-overhaul.md` should be reconstructed from the merged PRs and the dotfiles ADRs, or left as a permanent gap.
- Whether the dotfiles-canonical `architecture/subagent-routing-policy.md` should be written, or the mirror's provenance header rewritten to claim ownership.

### Artifacts

- `skills/cook/SKILL.md` — lines 47-57 (Fan pathway), 55 (the reference), 129 (post-merge integration pass)
- `skills/cheese/references/routing-policy.md` — lines 3, 5, 16
- `.hallouminate/wiki/architecture/ultracook-agent-topology.md`
- `.hallouminate/wiki/architecture/age-fanout-router.md`
- `src/fanout/curd_block.py` — `MAX_WAVE_SIZE`, `_wave_errors`
- `/Users/paul/Dev/dotfiles/.hallouminate/wiki/adr/cheese-factory-workflow.md` — ADR-001..009
- `/Users/paul/Dev/dotfiles/.hallouminate/wiki/architecture/saved-workflows.md`
- https://github.com/paulnsorensen/easy-cheese/pull/314 (open), /315, /316, /317 (merged)
- `~/.claude/workflows/cheese-factory.js` — the personal global Workflow script

### Suggested skills

`/cure` once the fork is resolved, scoped to whichever option is chosen. If the answer is option 2, run `/mold` first: porting ADR-006 changes enforced phase-chain invariants and deserves a spec rather than a direct edit.

### Environment

Branch `paulnsorensen/cheese-factory-refs`, clean at `0fa5e58a`. Workspace `/Users/paul/conductor/workspaces/easy-cheese/bissau`, target branch `origin/main`. No secrets involved. A sibling workspace named `cheese-factory-refs` exists and was not inspected this session.
