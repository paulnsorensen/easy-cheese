# Merge-conflict resolution

When `affinage.pyz pr-status` reports `merge.mergeable: CONFLICTING` or `merge.state: DIRTY`, the PR cannot merge until conflicts are resolved. `/affinage` does not resolve conflicts by hand — it routes to `/melt`, which runs the structural cascade (mergiraf → rerere → kdiff3).

1. Materialise the conflicts locally: `gh pr checkout <pr>`, then `git merge origin/<base>`. (`gh pr checkout` neither opens nor updates the PR, so it does not breach the no-`/gh` rule.)
2. Hand off to `/melt`. It first checks for squash-merge residue and stops with remedies if found — surface those verbatim and do not auto-apply.
3. After `/melt` resolves cleanly, the resolution commit is owned by `/melt` / `/cure`. `/plate` owns the verified commit and existing-PR update transaction.

- **Default and `--auto` mode**: run the checkout + `/melt` automatically before dispatching `/cure`, then re-run `affinage.pyz pr-status` to confirm `mergeable` cleared. If `/melt` cannot resolve (manual kdiff3 needed, or squash residue), write `status: halt: merge-conflicts-need-human` and stop.
- **`--safe` mode**: gate the checkout + `/melt` behind the handoff prompt — offer "Resolve merge conflicts" alongside the cure-selection options.
