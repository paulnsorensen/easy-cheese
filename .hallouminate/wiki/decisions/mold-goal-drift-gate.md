# Mold goal-drift gate and altitude tag

**Status:** accepted, 2026-09-05.

## Problem

Every Mold anti-drift gate before this change was noun-level and bottom-up: agent-introduced scope, the non-goals audit, and entity-referent binding all ask "did the user type this noun" or "does the code have this referent". The bounds pass captured the goal once, and nothing re-rendered or re-checked it. A dialogue could spend many grounded rounds on a fork (retry policy, say) whose every noun traced to the user while the pinned goal ("users can resume a session") never moved. The fork-round cap only fired on rounds that added no new evidence, so a rabbit hole with a fresh shape check per round never tripped it.

## Decision

Three prose rules plus one mechanical check, all in `skills/mold/`:

1. **Pinned goal.** The bounds pass pins one sentence on a `Goal:` line at the top of the ledger. It repeats verbatim every round and changes only through an explicit user fork.
2. **Altitude tag.** Every `Asking` fork names the acceptance criterion, public seam, or non-goal it moves. A fork that moves none is `[AGENT-DECIDED]` or a follow-up candidate, never a user question. This is the operational test for "devil in the details versus cruft": the devil changes Acceptance or an Interface sketch; cruft changes neither.
3. **Second round-cap trigger.** Three consecutive forks that fail the altitude tag force the decision map, same as three evidence-free rounds.
4. **`goal-drift` in the taste test** (`src/easy_cheese/shared/taste_test.py`). The ledger JSON may carry a top-level `goal` string. When present, the draft's `## Problem statement` (aliases `## Problem`, `## Goal`) must contain it verbatim (case-insensitive, whitespace-normalised). A reworded or dropped goal fails as `goal-drift`; a missing section fails as `missing-section:goal:problem`; a goal-less ledger skips the check.

## Why verbatim text, not judgment

The taste test is a mechanical host-side validator, not a fresh-context reviewer. A substring check is deterministic, cheap, and gives a precise failure mode. "Does this fork serve the goal" is a judgment and stays in prose (the altitude tag), where the user can argue with it. The verbatim rule also makes goal amendments visible: changing the sentence requires an explicit user fork, so a silently reworded goal fails the gate rather than passing on a paraphrase.



## Gotcha: the ledger has two shapes, so parse the goal once

`_normalize_ledger` accepts both `{"goal": ..., "forks": [...]}` and an id-keyed mapping `{"F-1": {...}, "F-2": {...}}`. The first cut parsed the goal in a separate helper and left the id-keyed fallback loop untouched, so a top-level `goal` key on that shape became a settled consequential fork named `goal` and every verdict failed `missing-fork:goal`. The fix (PR #620) reads the goal inside `_normalize_ledger` and skips the reserved key there. Any future top-level ledger key must be reserved in that same loop. Goal headings also live in their own `_GOAL_HEADINGS` set, matched exactly, rather than in `_REFLECTION_ALIASES`, because that table doubles as the `ForkCoverage.reflected_in` validator and anything added to it becomes a legal fork reflection target.

## Rejected

- **A new handshake checklist box / gate-graph node.** The gate-prose-sync test would require a model change and a `mold.dot` regen for what is a sub-check of the existing fork taste gate. Folded into `acceptance_gaps` instead.
- **Counting orphan Decisions as cruft in the taste test.** Already enforced: every settled consequential fork must reflect into Acceptance and Interface sketches (`missing-reflection`). The gap was goal-relative, not reflection-relative.
