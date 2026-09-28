# Wheypoint phase delta contract

This contract covers the durable revision written at the end of the Cook, Press, Age, or Cure phase.
The record is keyed by the phase slug and work id.
A terminal phase handoff writes its phase artifact and then commits one revision for that phase.
Mold publication and Plate publication do not call this writer and do not create a wheypoint revision.
No plugin hook is part of this contract. Issue #654 ask 4 (a `/compact` hook that emits the grounded manifest) is deferred follow-up work until a host-neutral compaction trigger exists; the compaction hook itself is host-specific and out of scope here.

## Entry resolution

Each phase uses its own archive for entry resolution: `python3 skills/<phase>/scripts/<phase>.pyz wheypoint-resolve --ref <slug>`.
Pass `--corpus-root <dir>` to read this project's corpus from another location; the writer accepts the same flag.
A corpus belonging to another project resolves but gates on `project-mismatch`, so the flag relocates a corpus rather than borrowing one.
`--corpus-root` is not accepted with `--legacy`, which reads a note beside the repository rather than any corpus; the pair exits `2`.
Plate also runs this command on entry, but only to resolve; it creates no revision.
The six outcomes are `authoritative`, `not-found`, `legacy`, `gated`, `ambiguous`, and `error`.
An `authoritative` record is the primary input.
Its `working_context` is authoritative and supplies the first batched `tilth_read`.
A `not-found` result proceeds cold.
A `legacy` result shows its source and slug before the phase proceeds.
A `gated`, `ambiguous`, or `error` result stops the phase and shows its payload.
Advisory findings display with any outcome.

A result with `source: phase-artifact` came from the first readable matching file in this order:
`.cheese/cure/<slug>.md`, `.cheese/age/<slug>.md`, `.cheese/press/<slug>.md`, then `.cheese/cook/<slug>.md`.
The handoff preamble parser supplies `phase_slug` from that file.
The result has outcome `legacy` and is not dispatchable as an authoritative record.
Show the source and parsed phase slug before using the artifact as context.

## Grounded context

A phase writer accepts one or more `--grounded path[#start-end]` arguments.
Paths are repository-relative files with optional one-based inclusive line ranges.
A first revision requires at least one grounded entry.
The writer accepts at most 16 grounded entries.
Supplying a grounded list replaces `working_context`; omitting it carries the existing context.
A `#` inside a file name is legal; the range is anchored on the last `#`.
`PR#<n>` and URL entries in `working_context` are pointers, not grounded paths; lint skips them.
The writer anchors relative paths and `.cheese/` at the git toplevel (or `--root`), never at the current directory.

## Writer exit codes

Exit `2` is caller usage: a bad `--grounded` entry or a first revision without one; nothing is written.
Exit `4` is a kernel failure before the artifact write; nothing is written.
Exit `5` means the artifact was written but the revision failed; stderr carries `wheypoint: artifact-orphaned <path>` and the next resolve gates on `stale-artifact-link`.
Every `wheypoint:`-tagged line on stderr is one plain-ASCII line, identical on every host.
A refusal, exit `2` or exit `4`, is reported as one stderr JSON line, `{"error": <message>, "exit_code": <n>}`, instead.
A successful write prints `wheypoint: revision work_id=<id> revision_id=<id> revision_number=<n> retried=<bool>`.
A stale-parent retry prints one `wheypoint: retry ...` line and one `wheypoint: retry outcome=...` line.
An unexpected failure always prints a traceback to stderr; set `EASY_CHEESE_DEBUG` or `CHEESE_DEBUG` to add one to deliberate refusals as well.

## Lint findings

`stale-artifact-link` is a gating finding.
It means a digest-bearing phase-artifact link is missing or no longer matches its recorded digest.
Stop instead of dispatching when this finding is present.

`stale-commit` is advisory.
It means the recorded repository commit exists but is not an ancestor of the current `HEAD`.
Display the code and detail with the resolved payload, but do not stop solely for this finding.

`grounded-path-missing` is advisory.
It means a path named in `working_context` is absolute, escapes the repository root, or is no longer a file; the detail names which.
Display the code and detail with the resolved payload, but do not stop solely for this finding.

Advisory findings never hide the outcome.
A gating finding remains a stop even when advisory findings are also present.

`link-pending` is advisory.
It means a sibling record holds an edge to this record whose reciprocal this record does not hold yet.
The next `checkpoint` of this record applies the reciprocal edge host-side.

`fork-pending` is advisory.
It means a child record was forked from this record and this record has not reconciled the fork yet.
The next `checkpoint` of this record applies the fork host-side; see [`work-graph.md`](work-graph.md).

`notes-long` is advisory.
It means `notes` holds more than 4000 characters; the hard limit is 6000.

## Work-graph keys in the resolve payload

The resolve payload carries two work-graph keys beside the outcome.

- `pending` lists the pending reciprocal links, then the pending forks; [`work-graph.md`](work-graph.md) gives both shapes.
- `bridge` is `{state, node_ref, wheypoint_ref}`, or `null` when no record resolved.
- `bridge.state` is `bound`, `bridge-inactive`, or `unbound`, and it never changes `dispatchable`.

A schema-3 link that holds only `path` reads as `repo:<path>`.
The kernel lint report records one receipt per such link in `normalizations`.
These receipts are data, never findings, and the resolve payload does not carry them.

A pending entry never changes the outcome or dispatch.
When the outcome is `gated` and `pending` holds a fork entry, `/cheese --continue` prints one line beside the gate:

```text
fork-pending: <child ref> takes <entry ids> at this record's next checkpoint
```
