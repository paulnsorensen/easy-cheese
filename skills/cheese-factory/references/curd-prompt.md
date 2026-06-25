# Per-curd worker prompt template

Loaded by `/cheese-factory` at Phase 2 (fan-out). Substitute `{N}`, `{slug}`, `{file_list}`, `{behaviour}`, `{acceptance_criterion}`, `{test_target}`, `{spec_summary}`, and `{hard_flag}` before dispatch.

```text
You are executing curd #{N} for spec: {slug}

## File Assignment (HARD CONSTRAINT)

You may ONLY modify these files: {file_list}

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
5. /commit (or git commit direct)            — single commit with conventional message
6. Write pr-metadata.json: {{title, body}} for the slicer to pick up later

## /age inline-degrade contract

You are running as a sub-agent. The /age skill must run its ten dimensions
INLINE within your own context — do not spawn sub-agents for parallel review.
Detection: invoke /age with the marker `invoked-from: cheese-factory-curd` in your prompt to /age; the skill switches modes.

## Quality gate

After /cure, run the project's quality gate command. If it fails, write
`status: halt: quality gate failed` in your handoff slug and stop — do not
attempt to fix.

## Handoff slug

Write `.cheese/cheese-factory/{slug}/curds/{N}.md` with:

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
- Call the host `Edit`/`Write` tool on a file you haven't `Read` this turn — prefer /cheez-write (it reads first); use host edit only as a fallback when tilth is unavailable.
- Invoke /pr-stack, /gh, or any PR-related skill.
- Chain forward (the orchestrator owns the chain).
- Retry on failure — write the halt and return; the orchestrator decides retry policy.
```

## Variant: `--hard` propagation

When `/cheese-factory` was invoked with `--hard`, substitute `{hard_flag}` with `--hard`. Otherwise substitute with the empty string. The flag flows through `/cook --hard --auto` and `/cure --hard --auto --stake medium+`. The curd worker does not invoke `/hard-cheese` directly; the gate fires inside `/cure`'s share-for-review handoff per `skills/hard-cheese/SKILL.md`.
