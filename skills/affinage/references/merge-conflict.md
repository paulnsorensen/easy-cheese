# Merge conflict resolution

A PR cannot merge when `pr-status` reports `merge.mergeable: CONFLICTING` or `merge.state: DIRTY`.
Send conflicts to `/melt`.
Do not resolve them by hand.
`/melt` runs mergiraf, rerere, and kdiff3.

1. Run `gh pr checkout <pr>`.
2. Run `git merge origin/<base>` to create the local conflicts.
3. Send the conflicts to `/melt`.
4. Show any squash residue remedy from `/melt` without changes.
5. Let `/melt` or `/cure` own the resolution commit.
6. Let `/plate` own the verified commit and PR update.

In default and `--auto` modes, run checkout and `/melt` before `/cure`.
Then run `affinage.pyz pr-status` again to confirm that conflicts are gone.
If conflicts remain, write `status: halt: merge-conflicts-need-human` and stop.

In `--safe` mode, require approval before checkout and `/melt`.
Include `Resolve merge conflicts` in the cure selection options.
