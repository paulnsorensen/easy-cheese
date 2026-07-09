# ADR: wheypoint provenance as additive header fields with join/split verbs

Status: accepted (2026-07-09)
Spec: session-convergence-wheypoint (dotfiles session; `/home/paul/Dev/dotfiles`)
Ships in: `skills/wheypoint/SKILL.md`

## Context

Interrupted or parallel agent-session threads could not be converged into resumable artifacts. `/wheypoint` handoff notes carried no machine-readable lineage — no session id, git anchor, creation time, or parentage — so joining two threads or forking one was untracked hand-work. The header schema stopped at `status / next / mode / artifact` + the orientation line.

## Decision

Extend the wheypoint header schema **additively** with four fields, placed after `artifact:` and before the orientation line, all **optional**:

- `session: <harness>:<session-id>` — auto-filled from the per-harness source map (claude: newest `*.jsonl` in the encoded-cwd projects dir; codex: `payload.cwd` in the rollout meta line; opencode: the `session` table). No user-supplied ids.
- `git: <branch>@<short-sha>` — the working anchor.
- `created: <UTC ISO-8601>` — capture time.
- `parents: [<slug>, ...]` — lineage; empty/absent for a fresh single thread.

Two verbs make lineage explicit:

- `/wheypoint --join <slugA> <slugB>` — writes ONE merged note with `parents: [A, B]`, consolidating both sources by reference (not re-paste).
- `/wheypoint --split` — writes TWO child notes, each `parents: [<current>]`, distinct slugs.

**Backward compatibility is the linchpin.** All four fields are optional, so pre-provenance notes stay valid, and `/cheese --continue` parses provenance-bearing and pre-provenance notes identically: the parser is **key-based** (`skills/cheese/SKILL.md` scans for `status:`/`next:`/`mode:`/`artifact:` by key), and the orientation line stays the **first non-key line** after the header block. No consumer couples orientation to "the line immediately after `artifact:`". A contract test locks the field placement (mutation-verified: moving a provenance line below the orientation line fails it).

## Gotcha — source the git short-sha from a granted command

wheypoint's `allowed-tools` grants only `Bash(git status:*)`, `Bash(git log:*)`, `Bash(git diff:*)`. Fill `git:` via `git log -1 --format=%h` for the short-sha (branch from `git status`). **Do NOT use `git rev-parse`** — it matches no grant and stalls under `--auto`. Adding a `rev-parse` grant was a deliberate non-goal; the sha is reachable under the existing grant.

## Why not the alternatives

- A frozen positional 4-line header (the shape `shared/scripts/handoff.py::parse_handoff_slug` still assumes): rejected — it can't carry lineage and already breaks on the long-standing `mode:` line. The key-based `/cheese --continue` path is the real consumer; the positional parser is a latent, uninvoked capability (`--phase notes` has no caller).
- Provenance in a sidecar file: rejected — splits the resumption contract across two artifacts; the note is meant to be read cold in one pass.

## Scope note

The historical short-sha of a *recovered* session is not in the session logs, so `/work-recovery --wheypoint` (the dotfiles-side sweep that writes provenance-bearing notes) fills `git:` branch-only — a schema-valid degradation, since every provenance field is optional.
