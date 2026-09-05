# Merge conflict resolution

A PR cannot merge when `pr-status` reports `merge.mergeable: CONFLICTING` or `merge.state: DIRTY`.
Send conflicts to `/melt`.
Do not resolve them by hand.
`/melt` runs mergiraf, rerere, and kdiff3.

1. Run `gh pr checkout <pr>`.
2. Run `git merge origin/<base>` to create the local conflicts.
3. Send the conflicts to `/melt`.
4. Show any squash residue remedy from `/melt` without changes.
5. Keep the resolved merge in the local working tree.
6. Let `/plate` own the resolution commit and the PR update.

In default and `--auto` modes, run checkout and `/melt` before `/cure`.
`/melt` leaves the resolution uncommitted.
Treat a resolved merge as a publishable change.
If `/melt` cannot resolve the conflicts, write `status: halt: merge-conflicts-need-human` and stop.
Run terminal `/plate` after every approved reply posts.
Then run `affinage.pyz pr-status` again to confirm that the conflicts are gone.

In `--safe` mode, require approval before checkout and `/melt`.
Include `Resolve merge conflicts` in the cure selection options.
