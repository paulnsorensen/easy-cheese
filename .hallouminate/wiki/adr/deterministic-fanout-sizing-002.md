# ADR-002 — The file-weight table is inverted: default full weight

**Status:** accepted · **Spec:** `deterministic-fanout-sizing`

## Context

Review fan-out was sized from raw `git diff` stats with no file-type weighting,
so lockfiles and generated blobs bought reviewers. Commit `0fa5e58` is 9504 raw
lines, of which 3546 is `Cargo.lock` and 793 is a JSON fixture.

The obvious fix — an allowlist of "real code" extensions — was drafted first and
**failed immediately in review**: it omitted `.rs` in a repo containing 4640
lines of Rust. That failure is not a slip, it is the shape of the mechanism. An
allowlist fails *silently toward under-reviewing* and is always one language
behind whatever the repo picks up next.

## Decision

Invert it. Default weight is **1.0**; subtract only positively-identified
non-review surface. First match wins.

| weight | matches |
|---|---|
| 0.0 | `*.lock`, `*-lock.json`, `*-lock.yaml`, `*.pyc`, `*.pyz`, `go.sum`, `fixtures/**`, `snapshots/**`, `vendor/**` |
| 0.25 | `README*`, `CHANGELOG*`, `docs/**`, `src/content/**`, `.hallouminate/**` |
| **1.0** | everything else -- **default** |

An unknown extension gets reviewed. A new language, a new directory, `.go`,
`.kt` -- all correct without anyone updating a table.

## Two matching shapes: bare filename vs. directory-scoped glob

A pattern is matched one of two ways depending on whether it contains `/`:

- **No `/`** -- basename-only. The pattern matches just the path's final
  segment (`fnmatchcase(basename, pattern)`), never the full path. This means
  the pattern names a *filename*, not anything whose path merely ends in
  those characters.
- **Contains `/`** -- anchored or nested. The pattern matches
  `fnmatchcase(path, pattern) or fnmatchcase(path, "**/" + pattern)`, so a
  pattern with a directory component matches that directory *anywhere in the
  tree*, not only at repo root.

This two-shape split exists because of a concrete defect: an earlier bare
`*lock.json` pattern (no leading hyphen) matched on substring-of-basename and
silently zeroed ordinary source such as `src/unlock.json` and
`src/config/deadlock.json`. A weight of 0.0 makes a file **invisible** to
sizing entirely -- exactly the silent under-review direction this ADR's
inverted table exists to prevent. The fix was the hyphenated forms
(`*-lock.json`, `*-lock.yaml`) plus the basename-vs-path split above, so a
lockfile pattern only ever matches a real lockfile basename.

Matching uses `fnmatchcase`, not `fnmatch` -- `fnmatch` applies
`os.path.normcase`, which would make this determinism-critical module
platform-dependent (case-insensitive matching on Windows, case-sensitive
elsewhere).

## Why the 0.25 tier survives

It was tested for its keep rather than assumed. Collapsing 0.25 into 1.0 changes
the tier of **4 of 30** commits, and every one is a docs commit being
*over*-sized. `publish cross-skill contract spec` moves 185 → 741, buying five
reviewers for a pure-documentation change. The tier stays.

## The easy-cheese-specific trap

In this repo `skills/**/*.md` and `agents/**/*.md` are the **product** — prompt
source, not documentation — and land at 1.0 via the default. A naive
code-vs-docs filter, which was the original framing of this work, would have
sized nearly every PR in this repo at `n=1` and reviewed nothing.

This is why the tiers are named by *review surface*, not by "code vs docs".

## Measured non-problems

Markdown reflow inflating line counts was suspected and measured: worst case 3×
on a 74-line change, 1.8× on a doc spec, 1.0× on the largest. Not worth a
word-diff pass. Recorded so it is not re-litigated.

## Consequence

An unconfigured repo fails safe — it slightly over-sizes docs PRs rather than
under-reviewing code. An optional `[review_surface]` TOML override may replace
the glob lists; its exact key layout is deferred to the first consuming repo.

Separately: a risk override retains the `effort=high` forcing regardless of
score. [ADR-001](./deterministic-fanout-sizing-001.md) governs `n` only and
is silent on `effort`, so this composition is recorded here since it is
otherwise unrecorded anywhere.

## Related

- [ADR-001](./deterministic-fanout-sizing-001.md) — override promotion
- [ADR-003](./deterministic-fanout-sizing-003.md) — no LLM in the sizing path
