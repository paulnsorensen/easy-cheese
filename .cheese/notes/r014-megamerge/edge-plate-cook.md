# Plate to Cook edge review

## State

broken

## Evidence

- Plate loads the topology reference for topology preflight and new pull requests (`skills/plate/SKILL.md:27-40`).
- Plate identifies repair branches with `worktree-agent-repair-*` (`skills/plate/references/topology.md:70-79`).
- Plate then follows Cook's merge-time topology policy (`skills/plate/references/topology.md:72-79`).
- Cook makes its quality gate reference the shared policy source (`skills/cook/SKILL.md:103-121`).
- Cook creates the repair branch from `origin/main` (`skills/cook/references/quality-gates.md:63-67`).
- The worktree command returns `{path, branch}` (`src/easy_cheese/shared/worktree.py:76-82`).
- Cook records only `slug`, `branch`, and optional `pr` (`src/easy_cheese_schemas/manifest.py:435-451`).
- Its validator requires only `slug` and `branch` (`src/easy_cheese/shared/fanout/validate_manifest.py:378-386`).
- Plate needs the originating run branch for the overlap check (`skills/cook/references/quality-gates.md:73-82`).
- Cook does not send that branch to the repair workflow (`skills/cook/references/quality-gates.md:63-67`).
- Cook passes `--open-pr` to terminal Plate for repair publication (`skills/cook/references/quality-gates.md:66`).
- Plate accepts new pull request work and applies its topology policy (`skills/plate/SKILL.md:31-40`).
- Both references agree on independent, harvest, and restack outcomes (`skills/plate/references/topology.md:75-79`; `skills/cook/references/quality-gates.md:79-82`).
- Plate has no runtime import or call into Cook (`src/easy_cheese/skills/plate/commands.py:8-34`).
- Plate emits no file or handoff to Cook. This edge uses linked instructions only.
- The Plate test checks only the repair branch prefix (`tests/python/test_plate_contract.py:13-32`).
- The Cook test checks only worktree creation and its output (`tests/python/test_baseline_policy_coherence.py:201-236`).
- No test exercises overlap detection, harvest selection, or restack selection.

## Blocker

- **Cook drops the run identity that Plate requires.** The repair branch contains a slug, not the verified run branch.
  Missing metadata is indistinguishable from a deleted run branch. Plate can select an independent pull request despite file overlap.
  Evidence: `skills/cook/references/quality-gates.md:63-67,73-82`; `skills/plate/references/topology.md:72-79`.
  **Fix:** Add required `run_branch` to `repair_dispatch`. Include it in the repair handoff. Validate it on both sides.
  Plate must halt when the field is absent. Plate must verify branch deletion before it selects the independent default.

## High

- **The small-overlap path names an interface that does not exist.** Cook calls `worktree_harvest(branch, onto=run_branch)` in its policy.
  The shared module exposes `harvest()` and the bundled `worktree harvest` command instead.
  Evidence: `skills/cook/references/quality-gates.md:81`; `src/easy_cheese/shared/worktree.py:85-101,150-164`; `skills/plate/references/topology.md:72-78`.
  **Fix:** Use `python3 skills/cook/scripts/cook.pyz worktree harvest --branch <repair-branch> --onto <run-branch> --repo <run-worktree>`.
  Resolve `<run-worktree>` from verified Git worktree state. Halt at topology when the command fails.

- **The mechanical overlap rule has no exact calculation.** Neither side defines the merge base, changed-line count, rename handling, or binary-file handling.
  Different calculations can select different publication topologies.
  Evidence: `skills/plate/references/topology.md:72-79`; `skills/cook/references/quality-gates.md:75-82`.
  **Fix:** Define one overlap command and one line-count rule. Define explicit results for renames and binary files.

## Medium

- **Tests do not exercise the seam from both sides.** Current tests protect the prefix and worktree creation only.
  Evidence: `tests/python/test_plate_contract.py:13-32`; `tests/python/test_baseline_policy_coherence.py:201-236`.
  **Fix:** Test the independent, harvest, restack, missing-branch, and failed-harvest outcomes through one shared topology interface.

## Low

none

## Contract changes not followed

- Cook added the repair topology, but its `repair_dispatch` type does not carry Plate's required run branch.
- Cook names `worktree_harvest`, but its command surface exposes `worktree harvest`.
- The branch prefix, publication permission, thresholds, and three outcomes agree.

## STE100 status

This note complies with STE100. The source prose does not comply.

- `skills/plate/SKILL.md:20,63,92,121,123` combines instructions. Lines 4-8 also use both `pull request` and `PR`.
- `skills/cook/SKILL.md:63,250` combines instructions.
- `skills/plate/references/topology.md:33-35,54,61` uses passive voice or combines instructions.
- `skills/cook/references/quality-gates.md:3,29,63-66` exceeds sentence limits or combines instructions.

## Follow-ups

- Add verified `run_branch` data to the repair dispatch and repair handoff.
- Use the exact bundled harvest command. Resolve the run worktree before harvest.
- Define the overlap calculation and its error results.
- Add seam tests for each topology result and failure path.
- Repair the listed STE100 violations.
