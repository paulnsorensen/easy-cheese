# Auto mode detail (cure)

Read this before running `/cure --auto --stake <floor>` for the fan-pathway exceptions, the puncture clause, and the empty-floor case.

## Per-finding flow

- Skip the selection-list rendering and the handoff gate.
- Auto-select every finding that meets the severity floor. Floor definitions: `selection.md` § Auto-mode selection.
- Apply findings one at a time. After each fix, run the narrowest test that proves it. If the fix breaks a previously-passing test or any project-wide gate, revert that single finding's edit and record it under `### Deferred` in the cure report with the test name and the failure summary. Continue with the remaining findings.
- After all selected findings are processed, skip the handoff gate and invoke `/age --scope <touched-paths> --auto` (forward `--open-pr` when it is in scope) so the chain can re-review.
- `/age --auto` enforces the two-pass cap. Cure does not need to track passes itself — it just keeps applying when invoked.

## Terminal publication

When the age child returns `next: done`, dispatch `/plate` once. It updates an existing PR automatically or, with `--open-pr`, applies the explicit-choice and review-shape policy before committing a new PR layout. After the publication lands, run the **§ Post-PR learnings write-back** (`post-pr-writeback.md`).

- **Orchestrated sub-agent exception.** A phase-only cure dispatched by `/cook`'s fan pathway never invokes `/plate`; the orchestrator owns commit and publication.
- **`/affinage` chain exception.** When `handoff_context.source_skill` is `/affinage`, suppress this terminal `/plate` — affinage posts its GitHub replies (final writes) and then owns terminal `/plate`.

**`--auto --hard` puncture clause.** When age returns `next: done`, dispatch `/plate --hard` rather than firing `/hard-cheese` directly. `/plate`'s final writing gate makes the completed artifact inventory visible to the metacognitive check. A failed hard gate halts publication; a non-TTY environment reports that `--hard` needs an interactive TTY.

If no findings meet the floor, write an empty cure report with `### Applied: (none — no findings meet <floor>)` and skip straight to the auto handoff with a one-line "auto chain clean" note.

## Within cook's own fan pathway (single-curd chain or a wave curd)

When `/cook`'s fan pathway (its retired-`/ultracook` mechanics, now self-hosted — see `skills/cook/SKILL.md` `## Fan pathway`) spawns cure as a phase-only sub-agent and owns the chain itself, honour the no-chain / no-push override:

- **Single-curd chain** — the spawn prompt says "for THIS PHASE ONLY" and "do not chain forward to the next phase." Apply the auto-selected findings, write `.cheese/cure/<slug>.md` (handoff slug at the top, `next: age`), and stop. Do not invoke `/age --scope <touched-paths> --auto`. The orchestrator reads the cure slug and spawns the next age itself.
- **Wave curd worker** — apply findings, write the cure slug, and stop. Do not invoke `/plate` or touch the remote; the fan pathway owns final commit and publication.

In both cases terminal `/plate` dispatch is suppressed — the orchestrator owns it.
