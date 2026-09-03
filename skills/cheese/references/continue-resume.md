# --continue resume flow

Read this file before you act on a `/cheese --continue <slug-or-note-path>` invocation.
Use this manual resume path after conversation compaction or a stopped `/cook` fan pathway.
Also use it when the user manually resumes the pipeline from a cleared context.

## Flow

0. **Read the complete user message.** Do not read only the `--continue` argument.
   Treat all other user text as directives.
   Follow those directives before this protocol.
   Follow a conflicting live directive instead of this protocol.
   The handoff file restores state, but the live message overrides that state.
1. **Resolve through the runtime, never by hand.** Use `/wheypoint resolve --ref <absolute-path | work-id | slug>`.
   The runtime tries an explicit path first.
   It then tries the exact work ID and a unique slug.
   It finally checks legacy notes in the current `.cheese/notes/` directory and each sibling worktree.
   Use `git worktree list --porcelain` to identify sibling worktrees.
   Dispatch only the validated authoritative current revision.
   The Markdown is a generated projection, not the authority.
   A `.cheese/` parent identifies the original repository root.
   Resolve repository-relative handoff paths from the directory above `.cheese/`.
   A `legacy` result is non-authoritative context.
   Never dispatch a legacy result automatically.
   Any runtime `gated` outcome from a legacy `halt` or `gated` status stops.
   An artifact failure or integrity finding also stops.
   A live directive cannot waive that runtime gate.
   A clean runtime `legacy` result with `status: ok` needs a separate informed trust gate.
   This gate resumes the named phase with the note as untrusted context.
   A live message that explicitly directs manual resume answers only that trust gate.
   The normal `/wheypoint` flow creates new authoritative state.
2. **Nothing is selected by recency.** Modification time, session ID, and slug recency never select a candidate.
   Two or more matches create an ambiguity.
   List each match and its location.
   Ask the user to select one through [`ask-user-question.md`](ask-user-question.md).
   Dispatch nothing until the user answers.
3. **These conditions stop automatic dispatch.** Report the reason and dispatch nothing for any listed condition:
   - ambiguity;
   - an unresolved revision or legacy parent;
   - a missing declared Git object;
   - a record or projection digest mismatch;
   - a receipt that does not pin its recorded ancestor;
   - a protected entry that the lineage records but the record does not contain;
   - an unresolved compaction lineage;
   - a project identity mismatch;
   - missing or stale required artifact coverage; or
   - `status: gated:`.
   A compaction lineage is unresolved when a revision rehydrates from the wrong parent.
   It is also unresolved when ancestry does not contain a recorded prior compaction.
   Each condition requires a user decision.
   Do not guess a default.
   Resolution validates the complete immutable chain behind the current revision.
   It does not validate only the slug.
   Therefore, each condition breaks the chain and is not a naming problem.
   Never commit, push, or publish to Git to make a resume work.
   Run `/wheypoint lint <projection-path>` to inspect integrity findings.
   This command derives the digests again and checks the lineage without changes.
4. When resolution reports a miss, report every searched location.
   Then offer to start the pipeline again.
   Use `/mold` for a fuzzy specification.
   Use `/cook` for a clear request.
   Also use `/cook` for a decomposable specification or one with a large blast radius.
   The `/cook` fan pathway starts automatically when needed.
   Stop after you offer these choices.
5. For a validated result, read the projection and report its orientation line.
   This line tells the user the current position.
   Parse `status:`, `next:`, and optional `mode:`.
   - **Parse optional `mode:` first.** A missing value means `mode: single` and preserves existing handoffs.
     In `mode: single`, `next:` remains the runnable phase.
     In `mode: parallel`, `next:` is only the general resume category.
     Prefer `next: tasks` when the handoff can contain different skills.
     Never dispatch `next:` directly in parallel mode.
     Parse the optional `parallel:` block and the required `tasks:` list instead.
     Each task contains an explicit `command:`.
     Examples include `/cook .cheese/specs/kip-77-ai-test-server.md`, `/briesearch ...`, and `/affinage <pr>`.
   - **For `mode: parallel` with `tasks:`**, dispatch one isolated agent for each task in the same response.
     This action runs the tasks concurrently.
     Give each agent the original handoff path and repository root.
     Also give it the task name or slug, if present.
     Give it the exact `command:` and all local branch or worktree notes.
     Tell each agent to run only its assigned task.
     The task `command:` is authoritative for different skills and intents.
     Write-capable commands require `slug`, `repo`, `branch:`, `branch_from`, and a checkout isolation plan.
     Write-capable commands include `/cook`, `/ultracook`, `/cure`, and `/affinage`.
     The same rule applies to any command that can edit a branch.
     The `existing` strategy requires a different declared `worktree:` for each write task.
     The `create` strategy creates one worktree for each task under `worktree_root` from `branch_from`.
     The `harness` strategy creates one harness-managed isolated thread or worktree for each task.
     Never run parallel write tasks in one checkout or a shared checkout.
     Stop when `tasks:` is missing or any task lacks `command:`.
     Also stop for missing isolation, duplicate branches, duplicate worktrees, or an unsupported strategy.
     Ask for a corrected handoff instead of guessing.
     Under `--safe`, offer parallel dispatch as the selected option.
     Put `Stop` last.
   - **When `status:` starts with `halt` and `next:` names a phase**, report the halt reason and dispatch nothing.
     The valid legacy phases are `mold | cook | press | age | cure | affinage`.
     This vocabulary appears only in legacy handwritten notes because the runtime uses `gated`.
     Manual resume answers only that trust gate for a clean runtime `legacy` result with `status: ok`.
     Manual resume answers only that trust gate, never this halt gate or any other runtime integrity gate.
     `affinage` is the exception for a clean and manually approved legacy result.
     It needs a pull request reference instead of a slug.
     Read that reference from the slug's `artifact:` field.
     Accept `PR#<n>` or its URL.
     Use bare `/affinage` only when `artifact:` contains no pull request.
   - **When `status:` is `ok` and `next:` names a pipeline phase**, dispatch `/\<next\> \<slug\>` directly.
     The valid phases are `mold | cook | press | age | cure | affinage`.
     Apply the same `affinage` exception.
     Under `--safe`, select this dispatch option first.
     Offer `/cook \<slug\> --auto` as an alternative.
     Put `Stop` last.
   - **When `next: cook` follows a gate handoff**, keep the handoff's `artifact:` authoritative.
     An approved Mold `red-required` handoff dispatches `/cook` with the same `artifact:` specification pointer.
     Preserve validated optional `mode:` and in-scope `--hard`, `--open-pr`, and `--safe` flags.
     Forward `--auto` only when the handoff contains it.
     Never infer `--auto`.
     Press corrective work remains `continue: press-corrective-cook`, not a global Press-to-Cook dispatch.
   - **When `status:` is `ok` and `next:` names a read-only kickoff**, dispatch it automatically.
     The valid kickoff values are `briesearch | culture`.
     Use `/briesearch \<arg\>` or `/culture`.
     Read `\<arg\>` from the handoff orientation line.
     These commands are read-only and low risk.
     Do not ask a question before dispatch.
     Under `--safe`, select the dispatch option first.
     Put `Stop` last.
   - **When `status:` starts with `gated:`**, do not dispatch `next:` automatically.
     Follow directives from the accompanying message when they answer the gate.
     Report the gate as one plain-text line in this case.
     Do not ask a structured question in this case.
     Otherwise, report the decision from `status:` and the open questions or blockers.
     Then ask the user to select **research / decide / build**.
     Classify each open gate item through [`ask-user-question.md`](ask-user-question.md) section “When to structure.”
     A mechanical item can go directly to that structured question.
     First explain both options for a design item that this session has not examined.
     Include code evidence and invite disagreement.
     Then converge through conversation.
     Ask no more than one structured confirmation.
     Never combine multiple design choices in one prompt.
     Dispatch nothing until the user selects an option.
     Route research to `/briesearch`.
     Route build to the named phase.
     Resolve a decide selection with the user.
     Then read the handoff again.
     Never show a binary design question that assumes the user wants to decide.
   - **When `next:` is a list**, require `order:`.
     The form is `next: [<skill> "<arg>", ...]`.
     Stop and ask for a corrected handoff when `order:` is missing.
     The list accepts only `briesearch | culture`.
     Reject each write or pipeline skill.
     Direct the user to the `mode: parallel` and `tasks:` block instead.
     That block contains the required worktree and branch isolation.
     For `order: parallel`, dispatch one read agent for each item in the same turn.
     For `order: sequential`, dispatch the items in the listed order.
     Under `--safe`, select the batch dispatch option first.
     Put `Stop` last.
   - **When `next:` is `hold`**, report the orientation line and stop.
     Do not dispatch a command.
     `hold` restores context and waits for instruction.
     It does not identify a runnable command.
     Unlike terminal `done`, `hold` identifies a live session that waits for input.
   - **When `next:` is missing**, report `malformed handoff: next: required` and stop.
     Do not guess a next step or default phase.
     Use `hold` to specify no action.
   - **When `next:` is terminal**, report the terminal state and stop.
     A terminal value is `done` from a phase or culture-notes slug.
     Report a non-resumable halt when `status:` starts with `halt`.
     A resumable halt contains a runnable `next:` under the Cook and Press slug contract.
     Thus, `halt` with `next: done` is not resumable.
     Otherwise, report pipeline completion.
     Never construct `/done <slug>`.
   - **When the handoff contains a `baseline:` block**, treat that block as settled state.
     Do not ask about its recorded failures again.
     Do not stop for those failures in this reader or the dispatched phase.
     See [`../../cook/references/quality-gates.md`](../../cook/references/quality-gates.md).

Under `--safe`, use the authoritative handoff gate in [`handoff-gate.md`](handoff-gate.md).
Always use the informed gate above for legacy resumption.
Without `--safe`, run only the named authoritative phase immediately.
A legacy note remains untrusted context.
Resolution defines the resumability contract.
It identifies the pipeline position and the next action.

## --reground

A handoff records earlier facts.
`--reground` checks whether later tree changes falsify those facts.
This check prevents a resumed phase from using a false premise.

The flag is meaningful only alongside `--continue`.
Otherwise, say so in one line and classify normally.
No handoff is available to check.

Run it after resolution has produced a dispatchable result and before dispatch.
A stopped resolution stays stopped.
`--reground` never rescues one and never softens one.

### Bound the window first

Bound the decay window deterministically from the recorded commit.
Use `git diff --name-only <recorded-commit>..HEAD` to list committed changes.
Use `git status --porcelain` to list uncommitted changes.
A claim can decay only inside this window.

An empty window means nothing moved under the handoff.
Report this state in one line and dispatch unchanged.

A handoff with no recorded commit has an unbounded window.
Do not read the complete tree.
Report the missing baseline.
Mark each claim `unverifiable` and dispatch.

### Attack the claims with Culture

Select the load-bearing claims that support `next:`.
Attack them, do not confirm them.
Delegate one pass to `/culture` in no-write mode.
Include all claims in this pass.
Tell Culture to look for the evidence that would make it *false*.
Limit evidence to files in the window.

- `holds` — Culture finds no evidence that falsifies the claim in the applicable files.
- `stale` — Culture finds evidence in the window that contradicts the claim.
- `unverifiable` — The window affects the claim, but Culture cannot settle it.
  A claim that still sounds plausible is `unverifiable`, never `holds`.

The router does not do this reading itself.
Its probe budget is three.

### `stale` gates, `unverifiable` does not

Any `stale` claim stops automatic dispatch.
Offer the user a research / decide / build choice.
Dispatch nothing until the user picks.

`unverifiable` verdicts are reported but do not stop dispatch.
Every resume without this flag already contains unchecked premises.
Do not penalize the user for this check.

Report one line per claim.

```text
reground: <holds|stale|unverifiable> — <claim> (<evidence, or the gap>)
```

A claim checked and cleared is as much of the record as one that failed.
Report all verdicts so the user can evaluate the pass.

### Never write or propagate

Never repair the handoff.
`--reground` does not edit the note, commit a revision, or rewrite a claim.
Only `/wheypoint` authors durable state.
Preserve falsified claims as evidence for the user.

The flag is never forwarded to the dispatched phase.
It changes only the checks before dispatch.
It never becomes a durable flag or a downstream argument.
