# Handoff gate templates

Read this when rendering either handoff gate `SKILL.md` § Handoff describes — the exact option wording for the cure-selection gate and the reply-approval gate.

## Cure-selection gate

Lead with the recommended composite, then present the four severity-floor options below it, in the same most-inclusive-to-least order, so the gate is predictable across every run:

- The five severity-floor options (recommended `all-medium, cheap`, then `all`, `all-medium`, `all-high`, `all-blocker`) are exactly age's — see [`../../age/references/handoff-detail.md`](../../age/references/handoff-detail.md) § Selection gate for their labels and semantics.

Then offer the non-floor options last:

- **Pick findings to fix** — free-text reply using `/age`/`/cure` verbs (`1,3,5`, `all-blocker`, `all-medium`, `all-high`, `cheap`, `all`, `none`, `skip N`).
- **Resolve merge conflicts** *(offered only when the PR has conflicts)* — checkout + `/melt` per `merge-conflict.md`, then re-render this gate.
- **Stop — leave the report for later** — equivalent to `none`.

The "present all four severity options on every run, empty-set-resolves-to-`none`" rule is age's — see [`../../age/references/handoff-detail.md`](../../age/references/handoff-detail.md) § Selection gate.

## Reply-approval gate

The single gate both Handoff branches use before any `post-reply` call:

- **Post pushbacks only** *(recommended)* — post `Reviewer-rejected` drafts; hold `Needs-investigation` items for investigation.
- **Investigate now, then post** — for each `Needs-investigation` item, run the follow-up investigation (`/pasteurize` for a regression test, `/briesearch` to explore the out-of-diff evidence), then post a reply carrying the actual result.
- **Post all** — post every drafted push-back and the explicit `Needs-investigation` follow-up notes (naming the needed evidence) without running the investigation first.
- **Skip posting** — leave the report for later; post nothing.
- **Per-finding** — free-text pick of which drafts to post or investigate.

## Cure dispatch context

On a non-empty cure selection (auto-selected by default or chosen at the gate), immediately dispatch `/cure <slug> [--safe] [--open-pr] [--hard]` with locked context:

```yaml
handoff_context:
  source_skill: /affinage
  source_report: .cheese/affinage/pr-<n>.md
  selection: "<verb or explicit ids>"
  resolved_ids: [<expanded ids>]
```

`/cure` re-confirms cited ids and goes straight to apply. Because the handoff carries `source_skill: /affinage`, `/cure` applies its fixes and runs its `/age --scope` loop but **suppresses its own terminal `/plate`** and returns — affinage owns publication. Propagate `--safe`, `--open-pr`, and `--hard` to `/cure` when in scope.
