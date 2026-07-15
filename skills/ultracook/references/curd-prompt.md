# Per-curd worker prompt template

Loaded by `/ultracook` at Phase 2 (fan-out). Substitute `{N}`, `{slug}`, `{file_list}`, `{behaviour}`, `{acceptance_criterion}`, `{test_target}`, `{spec_summary}`, and `{hard_flag}` before dispatch.

````text
You are executing curd #{N} for spec: {slug}

## File Scope (HARD CONSTRAINT)

Your curd implements behaviour: **{behaviour}**

You may ONLY modify files directly required by that behaviour. The intended file list is: {file_list}

That list was produced at decomposition time and may be stale — if the codebase has moved since then,
add or substitute files the behaviour genuinely requires, staying inside your behaviour's scope.
You only know your own file list, not what sibling curds own, so do NOT widen scope speculatively.
If the behaviour forces you onto a file outside `{file_list}`, note it in your handoff slug
(`expanded scope: <file> — <why the behaviour needs it>`) and proceed; the orchestrator detects
genuine cross-curd file conflicts when it merges the curds.

Exception: `pr-metadata.json` in your worktree root (you write that yourself).

## Behaviour

{behaviour}

## Acceptance criterion

{acceptance_criterion}

## Test target

Run ONLY this test command after implementation: {test_target}
Do NOT run the full test suite.

## Spec summary

{spec_summary}

## Workflow (single inline pass per skill)

1. /cook --auto {hard_flag}                  — implement the behaviour against the acceptance criterion
2. /press --auto                             — adversarial test hardening (single pass)
3. /age --auto                               — ten-dimension review of YOUR diff only, inline-degrade
4. /cure --auto --stake medium+ {hard_flag}  — fix every medium-or-above finding + cheap (contained-fix) lows
5. /plate (commit-only mode)                   — single Conventional Commit; no publish or layout question
6. Write pr-metadata.json: {{title, body}} for the slicer to pick up later

## /age inline-degrade contract

You are running as a sub-agent. The /age skill must run its ten dimensions
INLINE within your own context — do not spawn sub-agents for parallel review.
Detection: invoke /age with the marker `invoked-from: ultracook-curd` in your prompt to /age; the skill switches modes.

## Quality gate

After /cure, run the project's quality gate command. If it fails, write
`status: halt: quality gate failed` in your handoff slug and stop — do not
attempt to fix.

## Handoff slug

Write `.cheese/ultracook/{slug}/curds/{N}.md` with:

```
status: ok | halt: <one-line reason>
next: merge | done
artifact: <path-to-richer-report-if-any>
<one-line orientation: what this curd did>
```

Set `next: merge` when the curd is ready to be cherry-picked into the orchestrator
branch. Set `next: done` if you halted.

## Do NOT

- Run the full test suite (test_target only).
- Push or create PRs (the orchestrator handles that).
- Modify any file not in your file list.
- Call an unanchored host `Edit`/`Write` tool on a file you haven't read this turn — prefer /cheez-write; use a harness-native snapshot/anchored edit fallback only when the selected backend preserves stale-write safety.
- Invoke /plate in publication mode, /gh, or any PR-related operation.
- Chain forward (the orchestrator owns the chain).
- Retry on failure — write the halt and return; the orchestrator decides retry policy.
````

## Variant: `--hard` propagation

When `/ultracook` has `--hard`, propagate it through the review chain. Curd workers use `/plate` only in commit-only mode, so they never fire `/hard-cheese`; the orchestrator's terminal `/plate --hard` owns that gate after final artifacts are verified.
