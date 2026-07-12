---
name: pr-stack
model: haiku
allowed-tools: Bash(gt:*), Bash(gh:*), Bash(git:*)
license: MIT
description: >
  Manage stacked PRs using whichever stacking tool is installed: Graphite
  (`gt`), git-town (`git town`), or GitHub's native `gh stack` extension.
  Detects which is available in the current repo, then drives the matching
  one via its per-tool reference (`references/gt.md`,
  `references/git-town.md`, or `references/gh-stack.md`). Use when the
  user asks to "create a stack", "stack a branch", "restack", "submit a
  stacked PR", "rebase the stack", "sync the stack", "track this branch",
  "the bottom PR merged, what now", "clean up after a stack merge", or
  invokes /pr-stack. If none is available, stop and tell the
  user — never fall back to ad-hoc `git push` chains. Do NOT use for
  staging or committing — hand off to a discovered /commit skill (plain
  `git commit` otherwise). Do NOT use for PR review traffic, comments, or
  CI checks — hand off to a discovered /gh skill (plain `gh` otherwise).
---

# pr-stack

Stacked branches: a chain of small branches each opening one PR, kept in
order across rebases and pushed as a group.

Three tools implement this workflow today. They share the same mental model
but live in different ecosystems:

- **Graphite (`gt`)** — third-party CLI, mature, requires a Graphite account
  (`gt auth`). Stack metadata lives in `.git/.graphite_repo_config`.
- **git-town (`git town`)** — third-party CLI, mature, no account and
  forge-agnostic (GitHub / GitLab / Gitea / Bitbucket / Forgejo / Azure
  DevOps). Branch lineage lives in local git config
  (`git-town-branch.<name>.parent`), so there's nothing to sign up for.
- **GitHub `gh stack`** — first-party `gh` extension (`github/gh-stack`),
  private preview as of 2026-05; repos must be allow-listed via
  [gh.io/stacksbeta](https://gh.io/stacksbeta). Stack metadata lives in
  `.git/gh-stack`. Uses standard `gh auth login` — no third-party account.

This skill picks whichever one the user has and drives it. It does not
emulate stacking with plain `git`.

## Detection — run before anything else

```bash
# gt available?
command -v gt >/dev/null 2>&1 && gt --version >/dev/null 2>&1

# gt initialized in this repo?
test -f "$(git rev-parse --git-dir)/.graphite_repo_config"

# gh stack extension installed?
# (gh extension list output is TAB-separated: <short-name>\t<owner/repo>\t<version>)
# Guard with `command -v gh` so the probe stays quiet when gh itself is missing
# — `2>/dev/null` on the pipeline doesn't catch the shell's own "command not
# found" message.
command -v gh >/dev/null 2>&1 \
  && gh extension list 2>/dev/null | awk -F '\t' '$2 == "github/gh-stack"' | grep -q .

# git-town available?
command -v git-town >/dev/null 2>&1 && git town --version >/dev/null 2>&1

# git-town configured for this repo? (non-empty trunk = set up)
git config --local --get git-town.main-branch >/dev/null 2>&1
```

**Pick the tool the repo is already set up for.** A tool counts as *usable
here* when it's installed **and** configured for this repo:

| Tool | Installed probe | Configured-for-repo probe |
| --- | --- | --- |
| `gt` | `command -v gt` | `.git/.graphite_repo_config` exists |
| `git town` | `command -v git-town` | `git config --local --get git-town.main-branch` non-empty |
| `gh stack` | `gh extension list` has `github/gh-stack` | no preflight — detected lazily when a remote op exits `4` |

Then:

- **Exactly one usable** → use it; read that tool's reference.
- **More than one usable** → prefer **`gt`** (GA, mature, and the repo may
  already track a stack), then **`git town`** (GA, no account,
  forge-agnostic), then **`gh stack`** (first-party but private preview).
  Tell the user which others are present and offer to switch.
- **Installed but not configured** → offer the one-time setup (`gt init`,
  or `git config --local git-town.main-branch <trunk>` — your trunk name,
  e.g. `main` / `master`; `gh stack` needs no repo init) and proceed.
- **None usable** → **stop.** Don't reach for `git push` chains. See
  "None installed" below.

Run the probes every invocation — the user's environment can change between
sessions.

## None installed

If detection finds none of `gt`, `git town`, or the `gh stack` extension,
surface this verbatim and stop:

> Stacked-PR tooling isn't available on this machine / for this repo. Install
> one of:
>
> - **Graphite CLI** — `brew install withgraphite/tap/graphite` (or
>   `npm install -g @withgraphite/graphite-cli@stable`), then
>   `gt auth --token <token from https://app.graphite.com/activate>` and
>   `gt init` inside this repo.
> - **git-town** — `brew install git-town` (or `choco` / `scoop` on
>   Windows), then `git config --local git-town.main-branch <trunk>` (your
>   trunk name, e.g. `main` / `master`; or the `git town config setup`
>   wizard) inside this repo, plus either `git config --local
>   git-town.github-connector gh` (reuse your `gh` auth) or a
>   `git-town.github-token` PAT. Works on GitHub, GitLab, Gitea, and more.
> - **GitHub native `gh stack`** — `gh extension install github/gh-stack`,
>   then make sure the repo is allow-listed at
>   [gh.io/stacksbeta](https://gh.io/stacksbeta) (private preview as of
>   2026-05).
>
> Once one of those is installed, re-invoke `/pr-stack` and I'll drive it.

Do not improvise with plain `git push` chains, parent-target wiring, or
manual PR linking — the value of this skill is the stack-aware machinery,
and faking it produces a worse outcome than telling the user the tool is
missing.

**Third failure mode — `gh stack` installed but the repo isn't allow-listed.**
The CLI installs anywhere, but remote ops (`submit`, `sync`, `link`) fail
with exit code `4` when the repo isn't on the private-preview allow-list.
If you see exit `4`, surface this and point the user at
[gh.io/stacksbeta](https://gh.io/stacksbeta). If `gt` is also installed
locally, offer to fall back to it for this repo.

## Mental model (shared)

- **Trunk** is `main` (or whatever the repo calls it).
- **Stack** is a chain of branches, each parented on the previous one. The
  bottom of every stack is trunk.
- **One PR per branch**, each PR targeting its parent branch. The chain
  reviews bottom-up.
- **Submit pushes the whole chain** and opens / updates one PR per branch.
- **Sync** pulls trunk, restacks every surviving branch onto the new trunk
  tip, and prunes branches whose PRs have merged.

All three tools implement this model. Command names diverge — see the per-tool
reference.

## After a PR in the stack merges

When the bottom (or any merged) PR lands, the rest of the stack needs to
follow trunk forward and the merged branch needs to drop out. This is a
distinct moment — don't wait for it to come up in normal "sync" cadence.

Run the tool's sync command:

| Tool | Command | What it does |
| --- | --- | --- |
| `gt` | `gt sync` then `gt submit --stack` | Fetches trunk, restacks survivors onto the new trunk tip locally, prompts to delete merged / closed branches. Then submit pushes the rebased survivors. |
| `gh stack` | `gh stack sync` (`gh stack submit` only if you have unpushed local commits) | GitHub already cascaded the rebase server-side at merge time; sync mostly pulls that state down and updates local refs. |
| `git town` | `git town sync --stack` | Fetches trunk, drops the merged branch, rebases the survivors onto the new trunk tip locally, and force-pushes them so the forge re-targets their PRs. |

Key divergence: with `gh stack` the survivors were already rebased by the
GitHub server when the bottom PR merged — your job is to **pull that state
down**, not to recompute it. With `gt` the rebase is local, so `gt sync`
does the actual work on your machine.

If sync hits a conflict (trunk and a survivor touched the same lines), drop
into the tool's conflict-recovery flow — `gt continue` / `gt abort`,
`git town continue` / `git town skip`, or
`gh stack rebase --continue` / `--abort`. Never reach for bare
`git rebase --continue`; the tool's metadata won't advance.

After sync succeeds, run `gt log short` / `git town branch` / `gh stack view` to confirm the
chain looks right before the next submit.

## Tool-equivalence cheat sheet

| Action | `gt` | `git town` | `gh stack` |
| --- | --- | --- | --- |
| Initialize stack metadata | `gt init` (repo-level) | `git town config setup` (repo-level) | `gh stack init` (per-stack) |
| Start a stack off trunk | `gt create` on trunk | `git town hack <name>` | `gh stack init` + `gh stack add` |
| Create branch on top | `gt create -am "msg"` | `git town append <name>` (then commit) | `gh stack add -Am "msg"` |
| Amend tip + restack children | `gt modify -a` | edit, then `git town sync --stack` | (edit, then `gh stack push`) |
| New commit + restack children | `gt modify -cam "msg"` | commit, then `git town sync --stack` | (commit, then `gh stack push`) |
| Inspect stack | `gt log short` (`gt ls`) | `git town branch` | `gh stack view` (`-s` short) |
| Pull trunk + restack | `gt sync` | `git town sync --stack` | `gh stack sync` |
| Cascade restack only | `gt restack` | `git town sync --stack --no-push` | `gh stack rebase` |
| Submit / update PRs | `gt submit --stack` (`gt ss`) | `git town propose --stack` | `gh stack submit` |
| Adopt a plain-git branch | `gt track` (any time) | `git town set-parent` (any time) | `gh stack init --adopt` *(init-time only)* |
| Move up / down in stack | `gt up` / `gt down` | `git town switch` (picker) | `gh stack up` / `gh stack down` |
| Continue after conflict | `gt continue` | `git town continue` | `gh stack rebase --continue` |
| Abort / skip halted op | `gt abort` | `git town skip` / `git town undo` | `gh stack rebase --abort` |
| Open existing PRs as stack | n/a | n/a (set parents, then `propose --stack`) | `gh stack link <PRs...>` |

When in doubt about flags, **always defer to the per-tool reference**, not
to memory — all three CLIs drift between versions.

## Rules (apply to all three tools)

- **Don't reach into `git rebase` mid-stack.** Use the tool's sync / restack /
  modify commands so children stay parented correctly.
- **Don't `git push` a single branch in a stack.** Use the tool's submit /
  push command — bare push skips the parent-target wiring and leaves the
  rest of the stack stale.
- **Stage deliberately.** All three tools follow the staged set the way
  `git commit` does. Stage by name by default; the per-tool stage-all
  flags shown in the references (`gt … -a`/`-am`, `gh stack add -Am`) are
  fine when you mean to stage every tracked change. Avoid blind
  `git add -A` outside that deliberate case.
- **One concern per branch.** That's the whole point of stacking — keep each
  PR reviewable in isolation.
- **After a rebase conflict, use the tool's `continue` / `abort`**, never
  bare `git rebase --continue` / `--abort` — the tool's metadata won't
  update otherwise.

## Handoffs

- Staging and crafting commit messages → a discovered `/commit` skill when
  available, plain `git commit` otherwise.
- PR review, CI checks, merge, comments → a discovered `/gh` skill when
  available, plain `gh` otherwise.
- Pre-commit hooks complaining → a discovered `/prek` skill when available,
  otherwise resolve the hook failure directly and re-stage.

## When to read references

- `references/gt.md` — full `gt` command surface (create / modify / sync /
  submit / track / log), install + auth, restack recipes, conflict
  recovery, monorepo / multi-trunk caveats. Read when detection picks `gt`.
- `references/git-town.md` — full `git town` command surface (hack / append /
  sync / propose / set-parent / ship), install + forge auth, conflict
  recovery, config keys, squash-merge gotcha. Read when detection picks
  `git town`.
- `references/gh-stack.md` — full `gh stack` command surface, install +
  waitlist, exit codes, conflict recovery, divergence from `gt`. Read when
  detection picks `gh stack`.
