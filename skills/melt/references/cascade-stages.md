# Cascade stages — branch-specific steps

Steps 0-3 (squash-residue check, diagnose, structural resolution, rerere/manual) run on every invocation and live in the main SKILL.md. Steps 4-7 and special cases below apply only when specific conflict types arise.

## Step 4 — Pick ours / theirs (mergiraf-unsupported files)

For shell, SQL, YAML, JSON, and other formats mergiraf does not parse, use `conflict-pick`:

```bash
# Take ours for every hunk
python3 ${CLAUDE_SKILL_DIR}/scripts/melt.pyz conflict-pick hooks/session-start.sh --ours

# Take theirs for every hunk
python3 ${CLAUDE_SKILL_DIR}/scripts/melt.pyz conflict-pick .gitignore --theirs

# Match by regex; matched hunks resolve, others remain
python3 ${CLAUDE_SKILL_DIR}/scripts/melt.pyz conflict-pick config.yaml --grep "timeout" --ours
```

## Step 5 — Lockfiles

Lockfile content has structure that text or AST merge cannot validate. Take one side and regenerate from the manifest:

```bash
# Auto-detect conflicted lockfiles, take theirs, regenerate, stage
python3 ${CLAUDE_SKILL_DIR}/scripts/melt.pyz lockfile-resolve

# Preview
python3 ${CLAUDE_SKILL_DIR}/scripts/melt.pyz lockfile-resolve --dry-run

# Take ours instead
python3 ${CLAUDE_SKILL_DIR}/scripts/melt.pyz lockfile-resolve --strategy ours
```

Supports `Cargo.lock`, `package-lock.json`, `yarn.lock`, `pnpm-lock.yaml`, `poetry.lock`, `Pipfile.lock`, `uv.lock`, `Gemfile.lock`, and `go.sum`.

## Step 6 — Debug mergiraf

When mergiraf is not resolving something it should, start with the `--debug` single-file inspection in step 2 of SKILL.md. Also check:

```bash
mergiraf languages | grep <extension>   # is the type registered?
git check-attr merge -- <path>          # should show: merge: mergiraf
```

Common causes:

- Extension missing from `~/.gitattributes` — regenerate after upgrade.
- Parse failure on one of the three versions — mergiraf falls back silently.
- Very large files (>1MB) skip structural merge.

## Step 7 — Maintenance

```bash
mergiraf languages --gitattributes > ~/.gitattributes   # after upgrade

git rerere status              # what is currently tracked
git rerere diff                # pending resolution diffs
git rerere forget <path>       # forget a bad resolution
git rerere gc                  # clean old entries
ls .git/rr-cache/              # browse the resolution database
```

## Special cases

### Whitespace-only formatting changes

If one branch ran a formatter while the other modified content, mergiraf can produce more conflicts because AST positions shifted. Resolution: run the formatter on the merged result after resolving conflicts.

### Unrecoverable state

If conflict state is unrecoverable, abort and start over:

```bash
git merge --abort        # or
git rebase --abort       # or
git cherry-pick --abort
```

`/melt` surfaces abort as an option; the user decides.
