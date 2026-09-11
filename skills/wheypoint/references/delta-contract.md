# Wheypoint phase delta contract

This contract covers the durable revision written at the end of the Cook, Press, Age, or Cure phase.
The record is keyed by the phase slug and work id.
A terminal phase handoff writes its phase artifact and then commits one revision for that phase.
Mold publication and Plate publication do not call this writer and do not create a wheypoint revision.
No plugin hook is part of this contract.

## Entry resolution

Each phase uses its own archive for entry resolution: `python3 skills/<phase>/scripts/<phase>.pyz wheypoint-resolve --ref <slug>`.
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

## Lint findings

`stale-artifact-link` is a gating finding.
It means a digest-bearing phase-artifact link is missing or no longer matches its recorded digest.
Stop instead of dispatching when this finding is present.

`stale-commit` is advisory.
It means the recorded repository commit exists but is not an ancestor of the current `HEAD`.
Display the code and detail with the resolved payload, but do not stop solely for this finding.

`grounded-path-missing` is advisory.
It means a path named in `working_context` is no longer a file inside the repository.
Display the code and detail with the resolved payload, but do not stop solely for this finding.

Advisory findings never hide the outcome.
A gating finding remains a stop even when advisory findings are also present.
