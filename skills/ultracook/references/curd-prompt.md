# Per-curd phase prompt template

Loaded by `/ultracook` for each top-level phase spawn. Substitute `{N}`, `{slug}`, `{phase}`, `{worktree_path}`, `{file_list}`, `{behaviour}`, `{acceptance_criterion}`, `{test_target}`, `{spec_summary}`, `{baseline}`, `{prior_handoff}`, `{review_context}`, and `{agent_resolution}`.

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

A first age whose committed artifact resolves to `action: done` clean-completes the curd — the parent records that age's review context as the final review identity and skips cure and final age. On any other resolver action all five phases run unless the action halts dispatch; only the final age may terminate the table.

For age phases, review exactly this explicit context and copy it into the age handoff:

```yaml
review_context: {review_context}
```

`review_context` contains `base_commit` (commit SHA), `reviewed_tree_oid` (tree object ID, including uncommitted state), `diff_hash`, and `scope`. Never call the tree object ID a head commit SHA.

## Resolution provenance

Copy this resolved record unchanged into the phase output:

```yaml
agent_resolution: {agent_resolution}
```

## Handoff

Join the inherited WorkRecord, commit this phase's versioned envelope and body through `handoff-commit`, and return its runtime-derived artifact path. Preserve `{agent_resolution}` in provenance; for age, include `{review_context}` in the declared phase payload. The parent calls `handoff-resolve` and owns the next dispatch. Every age chooses `next_phase: done` only when publishable; a final-age destination of `cure` stops the curd.

Do not push, publish, harvest, plate, spawn another phase, or run outside `{worktree_path}`.
````
