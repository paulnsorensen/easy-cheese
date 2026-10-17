# Cascade stages — branch-specific steps

Steps 0 through 3 apply to every invocation.
The main skill file defines the squash check, diagnosis, structural resolution, and manual resolution.
Use steps 4 through 7 only for the specified conflict types.

## Step 4 — Select ours or theirs

Use `conflict-pick` for a file that mergiraf cannot merge.
Read the `mergiraf_supported` field and the `recommendation` field from `conflict-summary`.
Run `conflict-pick` when the recommendation names that command.
Do not use a static format list.
Mergiraf changes its language support between releases.

```bash
# Select ours for every hunk.
python3 skills/melt/scripts/melt.pyz conflict-pick hooks/session-start.sh --ours

# Select theirs for every hunk.
python3 skills/melt/scripts/melt.pyz conflict-pick .gitignore --theirs

# Select ours only for hunks that match the regular expression.
python3 skills/melt/scripts/melt.pyz conflict-pick config.yaml --grep "timeout" --ours
```

The command leaves unmatched hunks unresolved.

## Step 5 — Resolve lockfiles

Text and AST merges cannot validate lockfile content.
Select one side and regenerate the lockfile from its manifest.

```bash
# Detect lockfile conflicts, select theirs, regenerate each lockfile, and stage it.
python3 skills/melt/scripts/melt.pyz lockfile-resolve

# Preview the changes.
python3 skills/melt/scripts/melt.pyz lockfile-resolve --dry-run

# Select ours instead.
python3 skills/melt/scripts/melt.pyz lockfile-resolve --strategy ours
```

The command supports these files:

- `Cargo.lock`
- `package-lock.json`
- `yarn.lock`
- `pnpm-lock.yaml`
- `poetry.lock`
- `Pipfile.lock`
- `uv.lock`
- `Gemfile.lock`
- `go.sum`

## Step 6 — Debug mergiraf

First, use the `--debug` inspection from step 2 in `SKILL.md`.
Then run these checks:

```bash
mergiraf languages | grep <extension>   # Confirm that mergiraf supports the file type.
git check-attr merge -- <path>          # Confirm that Git uses mergiraf.
```

Common causes:

- The extension is absent from `~/.gitattributes`. Regenerate the file after an upgrade.
- One of the three versions has a parse failure. Mergiraf then uses text merge.
- Mergiraf skips files larger than 1 MB.

## Step 7 — Maintain resolution data

```bash
# Regenerate attributes after an upgrade.
mergiraf languages --gitattributes > ~/.gitattributes

# Show paths with recorded resolutions.
git rerere status

# Show pending resolution differences.
git rerere diff

# Remove a bad resolution.
git rerere forget <path>

# Remove old entries.
git rerere gc

# List the resolution database.
ls .git/rr-cache/
```

## Special cases

### Changes that modify only whitespace

A formatter on one branch can move AST positions while the other branch changes content.
Mergiraf can then produce more conflicts.
Run the formatter on the merged result after you resolve all conflicts.

### State that cannot be recovered

Offer an abort when the conflict state cannot be recovered.
The user decides whether to abort.

```bash
git merge --abort
git rebase --abort
git cherry-pick --abort
```
