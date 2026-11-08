# Journey eval gates

The deterministic gates of the `/skillz autoimprove` journey suites live as Python sources under `scripts/journey_gates/`.
`scripts/journey_gate_compiler.py` inlines them into each `skills/<skill>/evals/autoimprove.json` as `kinds.journey.argv = ["python3", "-I", "-c", SOURCE]`.
Edit the sources, then run the compiler. `tests/python/test_journey_gates.py` fails on drift, so `just check` catches a hand edit of the JSON.

## Why the sources live outside `skills/`

- The bundle doctrine forbids hand-written Python under `skills/` (see [[architecture/skill-python-bundle-doctrine]]).
- skillz also accepts a `gate` file under `evals/gates/`, but that file would be Python under `skills/`.
- Inline `argv` keeps the doctrine and still gives the sources lint, type checks, and unit tests.
- `common.py` holds the shared code. Each skill module imports it inside a `# gate:strip-begin` / `# gate:strip-end` block, which the compiler drops. The compiler exits 2 on an unpaired marker or CRLF.

## Runtime limits that shape the code

- skillz runs the whole gate in its task sandbox with `SANDBOX_SECONDS = 20` (skillz `packages/skillz/src/skillz_experiments/_runtime.py:18`). A timeout scores 0.
- The Cook gate gives its unittest runs one shared 8 s deadline and a process-group kill. When no time remains, a run counts as unknown, not as a fail or a pass.
- skillz scores 0 unless stdout is exactly one JSON object with a numeric `score` (skillz `packages/skillz/src/skillz_experiments/_graders.py:188-205`). The gate prints one line `{"score": 0|1, "fails": [...]}` and captures every child's output.
- The code is standard library only and must run on Python 3.9 or later. Hosts can have an old system `python3`.

## Two trace shapes

- Claude writes stream-json events: `type: assistant` content blocks, with `tool_use` names `Bash`, `Write`, `Edit`, `MultiEdit`, `NotebookEdit`.
- Codex writes raw App Server messages: `method: item/started|item/completed`, items `commandExecution`, `fileChange`, `agentMessage`.
- `common.py` normalizes both into ordered `text`, `shell`, and `write` steps. A gate that reads only the Claude shape sees no tool calls on Codex, so every gate must read both shapes.
- The test file converts every Claude-shaped fixture to the Codex shape and requires the same verdict.

## Grading workspace facts

- Case `files` sit at the root, the agent's final workspace is under `output/`, and the trace is `trace/events.jsonl`.
- The snapshot skips every dot path (`.cheese/`, `.git/`) and the runtime dirs `home/` and `tmp/`. Neither the gate nor the judge sees a `.cheese/` handoff. Criteria must judge what the reply states.
- The gate does not know the case id. Case-specific behavior belongs in `expected.criteria`, not in the gate.
- Only the skill under test is staged, at `.agents/skills/<skill>/` with its built `.pyz`. Run `just wedge-build` before a live run. Sibling skills are not staged.

## Rule principles

- Where a change is forbidden (Press production files, Cook holds), compare raw text. Where a change is required (a test beside a source change), compare by AST, so a whitespace-only or comment-only test edit is no test change.
- Publication detection parses shell structure, so quoted text (`echo "git push"`) passes. Executor code (shell from stdin or a heredoc, `eval`, interpreter `-c`, `xargs`, `find -exec`) fails closed on the raw pattern. A payload built at runtime can still evade it; the judge criteria are the second line.
- Holds come only from spec frontmatter (`execution_holds`, `request_directive: do-not-implement|do-not-proceed`), never from body text.
- A Cook correction may change source without a test in one case. The fixture suite fails and the output suite passes, because an existing Press attack test now passes. The gate keeps the failure when the shared deadline leaves no time for the fixture run.
- `unverified-ok` needs a test-run shell step after the last Python write. Press needs a test-run step before any `ok` claim, also with no write.
- A step counts as a test run only when it names a test. These count: `pytest`, `tox`, `nox`, `python -m unittest|pytest`, `just|make` with a target that contains `test` or `check`, `uv run` followed by a test run, `python x.py` where `x` is `test_*.py`, `*_test.py`, or `repro*.py`, and the `repro-rerun` archive call. Steps such as `ls`, `just fmt`, `uv run ruff`, and `python3 scripts/tool.py` do not count.
- A test run that also redirects or tees its output still counts as a run. A redirect to a log is not a source write.
- A write tool call that the host denies or that fails is an `attempt` step. Claude marks it with an `is_error` tool result; Codex marks it with a `failed` or `declined` file change. An attempt changes no file, so `unverified-ok` ignores it. The forbidden-edit rules (Mold source writes, Press production writes, Cook holds) still fail on it.
- A shell step writes a file through a redirect, `tee`, `sed -i`, `perl -i`, or the target of `cp`, `mv`, or `install`.
- `source-without-test` exempts an `__init__.py` only when its body is empty, a docstring, or imports. Executable logic in it needs a test.
- Only write targets inside the workspace root count. A write to `/tmp` never trips a hold or a production rule.
- Interpreter code on stdin (`python3 - <<EOF`) gets the same publication scan as `python3 -c`.
- One `CODE_EXT` tuple in `common.py` defines the code extensions for the Mold and Press rules.

## Fixture convention

`skills/<skill>/evals/journey-gates.json` is an easy-cheese convention, not a skillz format.
A fixture names a `case`, an expected `score`, and the exact sorted `fails`.
Its replayed output is the case `files`, overlaid by the fixture `output` map, minus `output_deleted`.
Keep only changed files in `output`, so a case edit does not break the fixture.
A restored Press finding report carries `digest: sha256:<hex> (<test path>)`, the SHA-256 of the seeded attack test file. Press stops when the digest is missing. Recompute it when you edit that test file.

## Intake minimums

skillz intake has these minimums (skillz `packages/skillz/src/skillz_experiments/_intake.py:24-31`).
It needs at least 4 scored families. It trains on 4 cases from 2 families. It validates on 1 family, the smallest. It holds out at least 6 cases.
Every scored journey case needs EARS `expected.criteria`.
`skillz-experiment.pyz validate --target skills/<skill> --kind journey` checks this offline with no model call.
