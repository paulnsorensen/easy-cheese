# Per-curd phase prompt template

Loaded by the `/cook` fan pathway for each top-level phase spawn. Substitute `{N}`, `{slug}`, `{phase}`, `{worktree_path}`, `{file_list}`, `{behaviour}`, `{acceptance_criterion}`, `{test_target}`, `{spec_summary}`, `{baseline}`, `{prior_handoff}`, `{review_context}`, `{model}`, `{effort}`, and `{agent_resolution}`.

`{model}` and `{effort}` are resolved per phase from the phase's role, per `skills/cheese/references/agent-resolution.md` § Phases x roles. They are never left unsubstituted so the spawn falls through to the parent's model.

````text
You are executing {phase} for curd #{N} of spec {slug}.

Worktree: {worktree_path}
Prior phase handoff: {prior_handoff}

## Behaviour and scope

Behaviour: {behaviour}
Acceptance criterion: {acceptance_criterion}
Intended files: {file_list}
Focused test: {test_target}
Spec summary: {spec_summary}
Baseline: {baseline} — the run manifest's classified `baseline:` block, carried down for the cook phase's baseline-vs-regression check; a curd never captures its own baseline.

Stay inside this behaviour. The file list may be stale; add only files directly required by the acceptance criterion and record any expansion.

## Phase

Run only `/{phase} --auto` for this curd, then stop. Do not chain forward. The parent dispatches the next fresh phase into the same worktree.

Phase sequence and types:

1. coder: cook
2. coder: press
3. reviewer: age
4. coder: cure (`--stake medium+`)
5. reviewer: final age

A first age reporting `next: done` clean-completes the curd — the parent records that age's review context as the final review identity and skips cure and final age. On any other `next:` value all five phases run and only the final age may terminate the table.

For age phases, review exactly this explicit context and copy it into the age handoff:

```yaml
review_context: {review_context}
```

`review_context` contains `base_commit` (commit SHA), `reviewed_tree_oid` (tree object ID, including uncommitted state), `diff_hash`, and `scope`. Never call the tree object ID a head commit SHA.

## Model

Model: {model}
Effort: {effort}

This phase runs at the model and effort resolved for its own role, not at whatever model the dispatching parent is running. A phase never silently inherits the parent model: if `{model}` arrived unresolved, halt rather than guessing one. Consecutive phases of the same curd routinely resolve differently — coder phases at the coder tier, age phases pinned to a powerful model at the age router's effort dial.

## Resolution provenance

The resolved model, power, and effort are recorded in `agent_resolution` (`resolved.model`, `resolved.power`, `resolved.effort`); that record, not the parent's model, is what makes the phase reproducible. Copy this resolved record unchanged into the phase output:

```yaml
agent_resolution: {agent_resolution}
```

## Handoff

Use the canonical `status:` grammar from the [handback contract](../../cheese/references/handback-contract.md). Write `.cheese/ultracook/{slug}/curds/{N}/{phase}.md` with:

```yaml
status: <canonical status field>
next: <next phase | done | cure>
artifact: <path-to-prior-report-if-any>
<one-line orientation>

agent_resolution: <shared block>
review_context: <required for age>
```

Every age writes `next: done` only when publishable. A final-age `next: cure` halts the curd. After the final age succeeds (or the first age clean-completes), return control; the parent invokes `/plate` commit-only and writes the aggregate `.cheese/ultracook/{slug}/curds/{N}.md`.

Do not push, publish, harvest, plate, spawn another phase, or run outside `{worktree_path}`.
````
