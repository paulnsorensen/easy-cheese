---
slug: install-sh-python-port
status: draft
created: 2026-05-30
confidence: medium
gates_overridden: []
agent_introduced_scope: []
---

# Partial shell→Python port of install.sh

## Problem

`scripts/install.sh` is 638 lines and the only shell script in the repo (Tier 1
+ Tier 2 of the succinctness pass already shed −341 LOC there). A few sections
fight bash's grain: `ec_parse_args` is 70 lines of manual `$1`/`shift` dispatch
plus two `--flag=value` mirror arms, `ec_resolve_harnesses` does whitespace
trimming through illegible parameter expansion (`${harness#"${harness%%[![:space:]]*}"}`),
and the `[[ "${EC_DRY_RUN:-0}" == "1" ]]` early-exit is hand-copied into 8+ call
sites. These are verified by reading the file `<certain>`. The argument-parsing
and string-munging logic is also the part the bats suite has to test through a
sourced-shell harness with filesystem stub binaries, when `mock.patch` would be
cleaner. The verdict from issue #70 stands: **partial port worth it; full port
not dramatic.**

## Goals

+ Move argument parsing, selection validation, and harness-list resolution into
  a tested Python module — the parts where bash's syntax is the liability.
+ Collapse the repeated dry-run early-exit into one Python construct.
+ Keep a thin, auditable bash shim that preserves the `curl | bash` UX verbatim
  (README §Install one-liners must keep working unchanged).
+ Land net LOC reduction (issue target: ~320–350 Python vs 638 shell) without
  losing any behaviour the bats suite currently pins.
+ Gain real unit testability via `mock.patch("shutil.which")` / monkeypatched
  `subprocess` instead of filesystem stub binaries on a sparse PATH.

## Non-goals

+ **Full port of the bash shim.** The `curl | bash` entrypoint stays shell. This
  is non-negotiable: the one-liner pipes a *single* file to `bash`, so it cannot
  `import` a sibling `scripts/install.py`. See Decisions for how the shim reaches
  Python.
+ Porting `command -v` availability checks, `brew`/`cargo`/`npm`/`uv`/`pipx`/`pip`
  install invocations, or the MCP-registration subprocess orchestration. These
  are thin wrappers over external CLIs where bash is already idiomatic and the
  Python version would be `subprocess.run([...])` boilerplate with no clarity win.
+ Changing any CLI flag, default, env-var override (`EC_*`), or user-visible log
  string. This is a refactor, not a behaviour change.
+ Cross-platform support (still macOS-only).
+ Touching the other `scripts/*.py` (build_pyz, gen_docs, release_notes,
  stage_release).

## Approach

Split by **which layer the code lives in**, not by function count:

1. **Port the pure-logic layer to `scripts/install_lib.py`** — argument parsing,
   selection validation, harness-list resolution, and the dry-run decision. These
   are deterministic string→data-structure transforms with no external process
   dependency. They get pytest coverage under `tests/python/test_install_lib.py`
   and the corresponding bats cases retire.

2. **Keep the orchestration layer in `install.sh`** — OS guard, `command -v`
   checks, every `brew/cargo/npm/uv/pipx/pip/gh/claude/crg/tilth` invocation, the
   `BASH_SOURCE != $0` test-source guard, and `ec_main`'s top-level sequencing.

3. **Define the seam:** the shim parses argv by *delegating to Python once*, gets
   back a normalized config (validated tool list, MCP list, resolved
   newline-delimited harness list, flags), then drives the install steps in shell
   using that config. Concretely, `install.sh` calls
   `python3 "$(dirname …)/install_lib.py" plan "$@"` and reads structured output
   (see Interface sketches). On parse/validation error Python exits non-zero with
   the message on stderr; the shim propagates the code.

**The `curl | bash` reconciliation (the hard part).** When run locally the shim
finds `install_lib.py` next to itself. When run via `curl … | bash`, only
`install.sh` reaches the machine — `install_lib.py` is not on disk. Two viable
seam designs; the spec recommends **Option A** and records B as the rejected
alternative for the human to weigh:

+ **Option A — shim self-fetches the Python module.** On `curl | bash` the shim
  detects it has no sibling `install_lib.py` (or `BASH_SOURCE` is not a real
  path) and `curl`s `install_lib.py` from the same `raw.githubusercontent.com`
  ref into a tempfile, then runs it. Adds one network round-trip and a
  ref-pinning concern (the shim must fetch the *matching* commit, not `main`,
  or the smoke test's `EC_SKILL_REF` invariant breaks). `<speculative>` this is
  the cleanest split but introduces a second remote dependency in the happy path.

+ **Option B — embed the Python as a heredoc inside the shim.** `install.sh`
  carries `install_lib.py` as a `python3 - <<'PY' … PY` heredoc, so one file
  still installs everything. No second fetch, no ref-pinning problem, `curl |
  bash` stays single-file. Cost: the Python lives inside a shell string, so it
  can't be imported by pytest as a module — you'd either keep a duplicate
  `install_lib.py` as the test target (drift risk) or extract-and-exec in the
  test (ugly). This **defeats the primary justification** (real unit testability),
  so it is rejected unless the network round-trip in A is judged unacceptable.

Recommendation: **Option A**, with the shim pinning its fetch to the same ref
the rest of the script already threads through `EC_SKILL_REF`. This preserves
both the single-command UX and the importable-module testability that motivates
the whole exercise.

## Port scope — function-by-function verdict

IN (move to `install_lib.py`):

+ `ec_parse_args` — **strong.** 70 lines of manual dispatch + `--flag=value`
  mirror arms → ~20 lines `argparse`. The clearest win; this is what the issue
  leads with.
+ `ec_validate_selection` — **in, rides with parse.** argparse `choices=` on a
  comma-split type validator replaces the `case " $allowed "` substring trick and
  emits a standard error. Belongs with parsing.
+ `ec_resolve_harnesses` (string layer) — **strong.** The `auto`/empty/comma-list
  branching plus per-token whitespace trim is `selection.split(",")` +
  `.strip()`. The illegible parameter expansion is the worst-readability code in
  the file. NOTE: the `auto` branch calls `ec_detect_harnesses` which runs
  `command -v` — that detection stays shell; Python resolves the *non-auto* and
  empty/error cases and the auto fallback message, taking the detected list (or
  the literal `auto`) as input. Define the seam so detection feeds Python, not
  the reverse (see Open questions).
+ dry-run decision — **in as data, not control.** Replace the 8+ copied
  `[[ "${EC_DRY_RUN:-0}" == "1" ]]` blocks' *decision* with a single
  `config.dry_run` boolean from Python. The shim still owns whether to `echo
  "would run …"` vs actually invoke, but reads one normalized flag instead of
  re-parsing the env var everywhere.

OUT (stay in `install.sh`):

+ `ec_tool_binary` — **out.** A 5-line `case`. Trivial in bash; a Python dict
  would be a net wash and forces a second seam crossing during the install loop.
+ `ec_cmd_exists`, `ec_detect_os`, `ec_ensure_homebrew` — **out.** `command -v`
  and `uname` wrappers; bash is the right tool.
+ `ec_brew_install_if_missing`, `ec_install_tilth`, `ec_install_tools` — **out.**
  Subprocess orchestration over `brew`/`cargo`/`npm`. Porting yields
  `subprocess.run` boilerplate with worse readability than the current shell.
+ `ec_install_mcp*` family (tilth/context7/tavily/crg + dispatch + list/for-harness
  loops) — **out.** Same reason: thin wrappers over `tilth`/`claude`/`crg`
  subprocess calls, plus harness-specific warnings. No clarity win.
+ `ec_install_crg_cli` — **out, and explicitly so.** CI sources the script and
  calls this function directly (validate.yml CRG smoke test). Keeping it a shell
  function preserves that test seam unchanged.
+ `ec_discover_skills`, `ec_install_skills`, `ec_install_skills_for_harnesses` —
  **out.** `gh api` discovery + per-skill `gh skill install` loop. Orchestration.
+ `ec_detect_harnesses` — **out.** `command -v` detection; feeds Python's
  resolver as input.
+ `ec_log`/`ec_warn`/`ec_err`/`ec_usage` — **out.** ANSI logging helpers and the
  heredoc usage text. `ec_usage` could move (argparse generates help) but the
  hand-written text is more readable than argparse's auto-format and the issue
  scopes help text as tolerable-in-shell.
+ `ec_main` — **out.** Top-level sequencing; calls the Python planner once, then
  drives shell steps.

## Decisions

+ Seam = **Option A self-fetch**, pinned to the same ref as `EC_SKILL_REF` —
  preserves single-command UX *and* importable-module testability; Option B's
  heredoc kills testability, the whole point.
+ New module is `scripts/install_lib.py` (mirrors the existing `scripts/*.py`
  convention: argparse, `from __future__ import annotations`, module docstring,
  pytest under `tests/python/`).
+ Python emits a **normalized config** the shim consumes; Python never invokes an
  installer. Clean logic/orchestration split (hexagonal-ish; CLAUDE.md §Loose
  Coupling).
+ `command -v`-dependent detection (`ec_detect_harnesses`) stays shell and feeds
  Python as *input* — Python's harness resolver must not shell out, so it stays
  unit-testable with no PATH mocking.
+ Retire only the bats cases whose function moved; keep bats for everything that
  stays shell. Net test surface shifts toward pytest, doesn't vanish.

## Interface sketches

```pseudocode
# scripts/install_lib.py
#   Pure logic. No subprocess, no `which`. Unit-testable with plain inputs.

@dataclass(frozen=True)
class InstallPlan:
    tools: list[str]          # validated against KNOWN_TOOLS
    mcp: list[str]            # validated; ["none"] sentinel preserved
    harness_selection: str    # raw: "auto" | "a,b,c"  (resolution needs detection)
    with_edit: bool
    dry_run: bool
    skip_tools: bool
    do_help: bool

def parse_args(argv: list[str]) -> InstallPlan        # argparse; raises SystemExit(2) w/ stderr on bad input
def resolve_harnesses(selection: str, detected: list[str]) -> list[str]
    # selection == "auto" -> detected or ["claude-code"] (+ warn)
    # else -> [h.strip() for h in selection.split(",")]; error on empty token

# CLI surface the shim calls:
#   python3 install_lib.py plan --tools … --mcp … …   -> prints KEY=VALUE lines or JSON to stdout
#   python3 install_lib.py resolve-harnesses <selection> <detected-newline-list-on-stdin>

# scripts/install.sh  (shim, abridged)
ec_load_lib() {
    # local sibling exists -> use it
    # else (curl|bash): curl install_lib.py @ pinned ref -> $TMPDIR/install_lib.py
}
ec_main() {
    eval "$(python3 "$LIB" plan "$@")" || return $?   # sets EC_TOOLS/EC_MCP/EC_DRY_RUN/...
    [[ "$EC_DO_HELP" == 1 ]] && { ec_usage; return 0; }
    ec_detect_os || { …; return 1; }
    [[ "$EC_SKIP_TOOLS" == 1 ]] || { ec_ensure_homebrew && ec_install_tools "$EC_TOOLS"; }
    detected="$(ec_detect_harnesses)"
    harnesses="$(printf '%s' "$detected" | python3 "$LIB" resolve-harnesses "$EC_HARNESS")" || return $?
    ec_install_skills_for_harnesses "$harnesses"
    [[ "$EC_MCP" == none ]] || ec_install_mcp_for_harnesses "$EC_MCP" "$harnesses" "$EC_WITH_EDIT"
}
```

## Risks

+ **`curl | bash` second fetch (Option A).** Adds a network dependency and a
  ref-pin requirement to the happy path. If the fetch fails or pins the wrong
  ref, install breaks in a way the current single-file script can't. Mitigation:
  fail loud with a clear message + manual-download fallback (README already
  documents the download-then-run path). This is the single biggest reason a
  human might prefer Option B or reject the port.
+ **`eval "$(python … plan)"`** to import config into shell is a code-injection
  surface if Python's output isn't strictly `KEY=value` with shell-safe values.
  All values here are from a closed `choices=` set or are harness names already
  trusted enough to pass to `gh skill install`. Still, prefer emitting quoted
  assignments or read structured output via a safer mechanism than bare `eval`.
+ **Two-language script** raises the contributor bar: a change to flags now spans
  `.sh` + `.py` + bats + pytest. The succinctness win must outweigh this.
+ **Behaviour drift during port.** The bats suite is the safety net; every
  retired bats case must have an equivalent pytest case before removal, or
  net-negative coverage results (Rule 9 — no faking completion).
+ **CI smoke tests** (`bash scripts/install.sh --skip-mcp`, sourced
  `ec_install_crg_cli`) must keep passing. The CRG smoke sources the file — the
  shim must stay sourceable with functions intact.

## Open questions

+ [TBD] Seam wire format: `KEY=value` lines + `eval`, vs JSON-on-stdout parsed by
  shell, vs Python writing a tempfile the shim sources. `eval` is simplest but
  the most dangerous; pick before /cook.
+ [TBD] `resolve-harnesses` seam: pass detected list on stdin (sketch above) or
  have Python invoke a passed-in detector? Keep Python subprocess-free — confirm
  stdin approach is acceptable.
+ [TBD] Does Option A's self-fetch need to honour `EC_SKILL_REF`, or a separate
  `EC_INSTALL_REF`? The smoke test pins skills to the commit under test; the lib
  fetch must match or CI tests a mismatched pair.
+ [TBD] Minimum Python version for `curl | bash` end users? CI uses 3.12; macOS
  system python3 may be older. argparse + dataclasses are fine on 3.7+, but
  confirm the floor.

## Quality gates

+ `shellcheck scripts/install.sh`: clean (CI gate, validate.yml).
+ `bats tests/bash/test_install.bats`: passes — remaining shell functions still
  covered; retired cases removed only after pytest equivalents exist.
+ `python3 -m pytest tests/python/test_install_lib.py -q`: passes — every retired
  bats behaviour has a `mock.patch`/monkeypatch-based equivalent.
+ `bash scripts/install.sh --dry-run`: byte-identical "would run …" output to the
  pre-port script for a representative flag matrix (diff-tested).
+ `bash scripts/install.sh --help`: unchanged usage text.
+ `bash scripts/install.sh --skip-mcp` on macOS CI: passes (real smoke test).
+ `source scripts/install.sh && ec_install_crg_cli`: still works (CRG smoke).
+ Net LOC: shell + new Python < 638, trending to the issue's ~320–350 Python
  estimate.
+ README §Install one-liners: run unchanged, verified by hand or a CI curl-equiv.

## References

Issue #70 (Tier 3 partial port); spun out of the scripts succinctness pass
(commit fe57d68 on `paulnsorensen/scripts-succinct-python-pass`).
