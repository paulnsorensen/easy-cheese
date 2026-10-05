# Stack provider setup

Load this reference from [`stacks.md`](stacks.md) when no stack provider is
usable, or when the user asks how to set up a provider for a team or a new
machine. Give the user the steps for the selected provider. Do not run
install, login, or init commands without approval.

## Configuration scope

Each provider keeps configuration in one of three scopes. Only shared scopes
reach a teammate or a second machine.

| Scope | Location | Shared with teammates | Repeat on a new machine |
| --- | --- | --- | --- |
| User | Home directory | No | Yes |
| Clone | `$(git rev-parse --git-dir)`, never committed | No | Yes, once per clone |
| Shared | A committed file or GitHub server state | Yes | No |

## Provider matrix

| | Graphite (`gt`) | Git Town | `gh stack` |
| --- | --- | --- | --- |
| Account per CLI user | Graphite account | None | None beyond GitHub |
| User-scope auth | `gt auth --token <token>` | `gh` connector or a token | `gh auth login` |
| Repository config | `gt init` writes `.graphite_repo_config` in the git dir | `git town init` writes `git-town.toml` | GitHub enables the repository |
| Config scope | Clone | Shared, after commit | Shared, server-side |
| Init on each clone | Yes | No | No |
| Reviewer tooling | None | None | None |

Stacked pull requests are ordinary GitHub pull requests. Reviewers need no
provider CLI or account.

## Graphite

Each CLI user needs a Graphite account. A reviewer does not.

1. On each machine, install `gt` and run `gt auth --token <token>`.
   Ephemeral hosts set `GRAPHITE_AUTH_TOKEN` instead.
2. In each clone, run `gt init`. The command records trunk in the git dir.
   Nothing is committed, so every teammate and every clone repeats this step.
3. To work on a teammate's stack, run `gt get <branch>`.

Graphite plans and open-source terms change. Tell the user to confirm
organization-repository access with Graphite before the team adopts it.

## Git Town

Git Town needs no account and no server.

1. One maintainer runs the `git town init` wizard once and saves to a
   config file. The maintainer then commits `git-town.toml`.
2. On each machine, each teammate installs `git-town` and sets forge access:
   `git config --global git-town.github-connector gh` reuses `gh` login.
   A token in `git-town.github-token` or `GIT_TOWN_GITHUB_TOKEN` also works.
3. A clone reads the committed trunk. It needs no init.

Keep forge tokens and the connector choice out of the committed file.

## `gh stack`

`gh stack` is a GitHub preview. Enablement is per repository.

1. A maintainer requests access at [gh.io/stacksbeta](https://gh.io/stacksbeta).
   GitHub enables the repository. All collaborators then have access.
2. On each machine, run `gh extension install github/gh-stack` and
   `gh auth login`.
3. A clone needs no init. GitHub holds the authoritative stack state.

The enablement preflight in [`gh-stack.md`](gh-stack.md) reports whether the
repository is enabled. Stacks cannot be driven from a fork.
