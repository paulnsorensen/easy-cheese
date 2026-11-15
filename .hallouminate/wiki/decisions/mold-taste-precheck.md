# Mold taste-test lexical pre-check and fork-id tags

**Status:** accepted, 2026-09-11. Fixes issue #660.

## Problem

`taste-test` runs two passes on one verdict: the reviewer's semantic pass and the host's lexical pass (`_mentions` in `src/easy_cheese/shared/taste_test.py`). The lexical pass ran only after the reviewer, so a draft that lacked a `(F-n)` tag on an Acceptance or Interface line failed as `unreflected-decision` after a semantic pass. The tag-only fix changed the draft digest, the verdict went stale, and the redispatch consumed one of the two correction rounds. Two multiplier specs hit round 3 and needed a `gates_overridden` rebind.

## Decision

- `taste-test --precheck --draft <d> --ledger <l>` runs `lexical_precheck`: ledger problems, applicability, goal drift, and `missing-section` / `unreflected-decision` for every settled consequential fork across `required_reflections(draft)`. It needs no verdict, prints `{"gaps": [...]}`, exits 0 when clean, and consumes no correction round. `--precheck` and `--verdict` are a required mutually exclusive argparse group.
- The spec template (`skills/mold/references/curdle.md` § Spec template, **Fork-id tags**) documents the convention: each line that reflects a fork carries `(F-n)`. `handshake.md` and `gate-graph.md` tell the author to run the pre-check before the reviewer dispatch.

## Rejected

- **Tag-stripped digest compare** (accept a rebind when the draft equals the verdict's draft with fork-id tags removed). It adds a second equality notion to the digest binding that `mold-goal-drift-gate.md` records as deliberate. The pre-check removes the need.
- **Documentation alone.** Authors still discover the failure late when they skip the template.

## Gotcha

`skills/mold/references/commands.md` is a generated region. Edit the `bundle_command` description in `src/easy_cheese/skills/mold/commands.py` and run `scripts/render_generated_regions.py`; a hand edit fails `--check` with `DRIFT`. basedpyright rejects implicit string concatenation in that description, so join long strings with `+`.
