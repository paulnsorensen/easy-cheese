# Release channels: next soak branch and stable main

## Decision (2026-08-29, PR #540)

The repo runs two branches:

- **`next`** — integration/soak channel. Every PR targets `next`
  (`gh pr create --base next`) and squash-merges there. Dependabot
  targets `next`. Push CI (`validate`, `build-pyz`), CodeQL, and
  dependency review all cover `next`.
- **`main`** — stable channel and GitHub default branch. Advances
  **only** by fast-forward promotion (`just promote`), which verifies
  FF-ability and a green `validate` run on `next` before pushing
  `origin/next:refs/heads/main`. Releases keep tagging `main`, so
  `release.yml`'s ancestry gate (tag must be an ancestor of `main`)
  is unchanged — tag after promoting, never on `next`.

## Why this design, not that one

- **Problem**: the maintainer's install floats the default branch via
  the dotfiles skill sync, so dogfooding a risky change (e.g. `cut`'s
  RED gates) previously required merging to `main` — every channel got
  it instantly, and the next tag shipped it unsoaked.
- **Rejected: lagging `release` branch off `main`.** Consumers already
  track `main` (npx skills add resolves the default branch); demoting
  `main` would migrate every install. Inverting to a `next` soak branch
  keeps every external channel untouched.
- **Rejected: promotion via PR.** A squash-merge to `main` rewrites the
  promoted SHAs and permanently breaks fast-forward parity between the
  branches. Promotion is always a direct FF push (admin bypass on the
  `main-protection` ruleset covers the PR-requirement rule; the
  `non_fast_forward` rule is satisfied by construction).

## Gotchas

- **Nothing lands on `main` directly.** Any direct squash to `main`
  diverges the channels and forces a `next` rebase.
- `next-protection` ruleset (id 21836182) mirrors `main-protection`:
  deletion + non-FF blocked, PRs required, admin always-bypass.
- Docs deploy, OpenSSF Scorecard, and `publish-pypi` stay main-only by
  design — publishing from an unsoaked branch would defeat the model.
- The maintainer's machine tracks `next` via `pin: next` in the
  dotfiles `skills/_registry.yaml`; the sync's
  `_cz_vendor_external_skills` refreshes branch pins on every sync
  (fixed alongside this change — previously a pin froze at clone time).

Channel rules for contributors live in CONTRIBUTING.md ("Release
channels") and AGENTS.md ("Release channels: PRs target `next`").
