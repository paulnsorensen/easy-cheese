---
name: ultracook
description: Pipeline one approved high-blast-radius spec sequentially through cook → press → age → cure → age → cure → age (all `--auto`), with fresh-context isolation per phase. Use when the user has such a spec — phrases like "/ultracook .cheese/specs/<slug>.md", "ultracook this", "run the full pipeline in isolation", "fresh-context auto chain", "send it through the cave", "pipeline with no contamination". Runs inline and spawns full-peer general-purpose sub-agents (one per phase), each invoking the phase skill with `--auto` and writing its handoff slug under `.cheese/<phase>/<slug>.md`. Sub-agents inherit the parent's model and full tool / MCP / skill access. Use when the user wants `/cook --auto`'s autonomous chain semantics but with each phase reasoning blind to prior phases. After `/mold`; ends after the third age spawn (or earlier on halt / early-stop).
license: MIT
---

# /ultracook

Use this skill when the user wants the whole `cook → press → age → cure → age → cure → age` chain to run forward without per-step approval, **and** wants each phase to reason in fresh context — blind to the previous phase's chain-of-thought.

Do not use it for short focused changes (`/cook --auto` is cheaper and continuous), for fuzzy planning (`/mold`), or for review-only work (`/age`).

`/ultracook` is the sub-agent-transport sibling of `/cook --auto`. Same seven spawns, same `--auto` semantics propagated end-to-end, same medium+ severity floor, same two-cure-pass cap. The only difference is that each phase runs inside its own freshly-spawned sub-agent, so the parent context never accumulates phase-internal reasoning and review is adversarial rather than continuous.

## Inputs

Accept one of:

- A spec path. When explicit, it points wherever the user wrote the spec.
- A bare slug whose spec lives in the per-project durable corpus (see `shared/formatting.md` § Corpus location).
- A pasted spec, with a slug supplied alongside.

`/ultracook` does not accept fuzzy or open-ended asks — those go to `/mold` first. The orchestrator assumes the contract is already locked.

Optional flag: `--open-pr` — at the terminal, open a *new* PR when none exists (the default only pushes an already-open one). The orchestrator performs the terminal push itself; the phase-only cure sub-agents never push.

## Flow

1. **Resolve slug** — derive `<slug>` from the input. If a spec path is given, the slug is the basename without `.md`; if a bare slug is given, confirm the spec exists at the durable path the spawned `/cook` resolves (`python3 ${CLAUDE_SKILL_DIR}/scripts/cook.pyz artifact-path specs <slug>`; see `shared/formatting.md` § Corpus location).
2. **Guard against re-entry** — if any of `.cheese/{cook,press,age,cure}/<slug>.md` already exist, stop with a one-line list of the existing handoffs and tell the user to either run `/cheese --continue <slug>` to resume from the latest phase or `rm` the relevant files to start fresh. Never silently wipe.
3. **Phase loop** — for each phase in `cook, press, age, cure, age, cure, age`, spawn a fresh sub-agent (see `## Sub-agent contract` below), wait for it to return, read `.cheese/<phase>/<slug>.md`, and decide:
   - `status:` starts with `halt` → surface the halt reason and stop.
   - `next:` is `done` and the phase is age → stop early with a clean summary (the diff is clean at the medium+ severity floor; cure has nothing to apply).
   - Otherwise → continue to the next phase.
4. **Terminal push** — after the third age spawn (or any earlier non-halt stop), if an open PR exists for the branch, dispatch `/gh` to commit + push the chain's changes to it (Rule 11 — the existing PR is the authorization). Open a *new* PR only when `--open-pr` is in scope. A halt never pushes.
5. **Final summary** — print a four-line summary: passes completed, total findings applied / deferred, the final age-report path, and whether the PR was pushed (or the next-step nudge "review the diff, then `/gh` when ready" if no PR existed and `--open-pr` was absent).

`/ultracook` opens a *new* PR only with `--open-pr`; otherwise it pushes to an already-open PR at the terminal and never creates one.

## Phases and slug paths

The chain is fixed: seven spawns. The orchestrator walks the table top-to-bottom and stops after the last entry.

Every spawn uses the canonical `/<phase> <slug> --auto` form. Cook accepts a bare slug per its Inputs section; the other phases already resolve their paths from the slug.

| # | Phase invocation                          | Handoff slug                  |
|---|-------------------------------------------|-------------------------------|
| 1 | `/cook <slug> --auto`                     | `.cheese/cook/<slug>.md`      |
| 2 | `/press <slug> --auto`                    | `.cheese/press/<slug>.md`     |
| 3 | `/age <slug> --auto`                      | `.cheese/age/<slug>.md`       |
| 4 | `/cure <slug> --auto --stake medium+`     | `.cheese/cure/<slug>.md`      |
| 5 | `/age <slug> --auto`                      | `.cheese/age/<slug>.md` (overwritten) |
| 6 | `/cure <slug> --auto --stake medium+`     | `.cheese/cure/<slug>.md` (overwritten) |
| 7 | `/age <slug> --auto`                      | `.cheese/age/<slug>.md` (final report) |

### Cap enforcement

The two-cure-pass cap is enforced by **chain length, not by age**. Each age sub-agent boots in fresh context and cannot count prior cure passes, so the contract cannot rely on age tracking the count. Instead:

- The chain table has exactly seven entries, with two cure spawns (#4 and #6) and three age spawns (#3, #5, #7). After spawn #7 completes, the orchestrator stops because the table is exhausted.
- Each age spawn writes `next:` from what it observes on its own run: `next: cure` when at least one finding meets the `medium+` floor (medium-or-above, or a cheap contained-fix low), `next: done` when none do. The field is **informational** under ultracook — it drives early-stop (when an age reports clean), but it does not gate cap enforcement.
- `/ultracook` does not pass a pass-ordinal hint to age. Age has no need to know whether it is age₁, age₂, or age₃; the orchestrator owns the position.

## No-chain isolation directive

Each phase's existing `--auto` contract chains forward in-session — `/cook --auto` invokes `/press --auto`, which invokes `/age --auto`, etc. `/ultracook` overrides that behaviour: every spawn must run only its own phase, write the slug, and stop. The orchestrator owns the chain.

The override travels in the spawn prompt as the explicit no-chain directive: `Do not chain forward to the next phase even though your auto-mode contract documents that. Write your handoff slug and stop. The /ultracook orchestrator is driving the chain.`

Each phase's SKILL.md `## Auto mode` section honours this directive — see `skills/<phase>/SKILL.md` `### When invoked from /ultracook` for the per-phase contract amendment. Without the directive, sub-agent #1 would run the entire pipeline inside its own context and the per-phase fresh-context property would not be delivered.

## Sub-agent contract — inheritance, not diminution

Each phase spawns a **full peer** sub-agent — same model as the parent, full tool access, full MCP access, full skill access. These are not focused mini-assistants:

- `/cook` writes code across the changed files.
- `/press` runs the project's test suite and adds tests.
- `/age` reviews ten dimensions over the diff.
- `/cure` applies fixes via `cheez-write` and re-runs test gates.

Diminutive defaults (haiku model, restricted tools, `Explore`-style read-only workers) will choke phases that need to edit dozens of files or run real test suites.

Concrete `Agent()` signature shape (harness-agnostic; adapt the keyword names to the host):

```
Agent(
  subagent_type: "general-purpose",   # never specialised
  # model: omit — inherits parent's model. Do not pass haiku/sonnet here.
  prompt: "Run /<phase> <slug> --auto for THIS PHASE ONLY. Write
           .cheese/<phase>/<slug>.md with the handoff schema and stop.
           Do not chain forward to the next phase even though your
           auto-mode contract documents that. The /ultracook orchestrator
           is driving the chain."
)
```

The sub-agent's stdout is operator-visible but **not** the chaining contract. The orchestrator must read `.cheese/<phase>/<slug>.md` to decide what happens next; never infer success or `next:` from the sub-agent's last line. Asking the sub-agent to echo its status to stdout would tempt a future maintainer to wire stdout-driven chaining back in.

Rules:

- **Do not downgrade the model.** Omit the model parameter so the sub-agent inherits the parent's model. Never pass a smaller tier (haiku, lighter task workers) for ultracook phases.
- **Do not narrow `subagent_type`.** Use `general-purpose` (or the harness equivalent that grants full tool access). Do not pass `Explore`, `lsp-probe`, or any other read-only / scoped worker type.
- **Do not restrict tools or MCP access.** Each phase needs Bash, Edit, Write, Read, the `cheez-*` skills, and any MCP servers the parent has. Restricting them is the failure mode the contract exists to prevent.
- **Do pass the slug.** The phase skill resolves its own paths from the slug; `/ultracook` does not pre-compute paths for the sub-agent.

The contract is "inheritance, not diminution" because most sub-agent patterns in this ecosystem (Explore, lsp-probe, whey-drainer, ricotta-reducer) are deliberately scoped down for cheap focused queries. `/ultracook` does the opposite: it spawns workers that are full peers of the parent, doing major work in their own context window.

## Handoff slug schema

Every phase writes its handoff slug to `.cheese/<phase>/<slug>.md` with the following minimum shape (prepended as frontmatter or inline at the top of richer reports such as age and press):

```markdown
status: ok | halt: <one-line reason>
next: <phase-name | done>
artifact: <path-to-richer-report-if-any>
<one-line orientation: what this phase did>
```

`status: ok` means the phase finished cleanly and `next` names the next phase the chain should run. `status: halt: <reason>` means the automatic `/ultracook` chain stops and surfaces the reason verbatim; `next` still names the next runnable phase if a human later chooses to resume via `/cheese --continue <slug>`. `next: done` is terminal: age writes it when the diff is clean at the medium+ severity floor (early-stop signal), and other phases use it only when no runnable resume phase exists. The two-cure-pass cap is enforced by chain length, not by `next: done` — see `### Cap enforcement` above.

For phases that already write rich reports (`/age`, `/press`, `/cure` once extended, `/cook` once extended), the slug schema is prepended at the top of the same file — there is no second file. The schema is the contract; the body is whatever the phase normally writes.

## When auto mode stops early

`/ultracook` stops and surfaces the report when:

- A phase's slug file is missing after the sub-agent returns (the sub-agent did not write its handoff — print "phase did not write handoff — check sub-agent logs").
- A phase writes `status: halt: <reason>` (a quality gate failed, press came back `blocked`, cure could not apply any finding). Surface both the halt reason and the slug's `next:` value when it is not `done`, so the user can explicitly resume later with `/cheese --continue <slug>`.
- An age phase writes `next: done` because the diff is clean at the medium+ severity floor (early-stop). Note: this only fires from age spawns; cure always writes `next: age` and cap-enforcement does not flow through `next: done` (the chain length handles that — see `### Cap enforcement` above).

In every early-stop case, surface the slug file path so the user can read the full report. The natural terminal case (chain table exhausted after spawn #7) does not need an explicit early-stop signal — the orchestrator simply runs out of entries to spawn.

## Existing handoffs

If any of `.cheese/{cook,press,age,cure}/<slug>.md` already exist when `/ultracook <slug>` is invoked, stop. Do not silently wipe — the user may be mid-pipeline. Scan all four phase paths and print only the ones that exist:

```
Slug `<slug>` has existing handoffs:
  .cheese/cook/<slug>.md     (when present)
  .cheese/press/<slug>.md    (when present)
  .cheese/age/<slug>.md      (when present)
  .cheese/cure/<slug>.md     (when present)
Use `/cheese --continue <slug>` to resume from the latest phase, or
`rm` the listed files to start fresh.
```

Removing the handoffs by hand is the only sanctioned reset path. The orchestrator does not accept a wipe flag — adding one would create a destructive default for what is intentionally a one-line `rm`.

## Output

A short final summary, after the chain stops (success or early stop):

```
Ultracook summary — <slug>
Passes completed: <list of phase names that ran>
Findings:         <fixed count> applied, <count> deferred (cure-report path)
Final age:        .cheese/age/<slug>.md
Next step:        review the diff, then /gh when ready
```

If the chain stopped on a halt, replace "Next step" with the halt reason and the path of the phase that surfaced it.

## Preferred tools and fallbacks

`/ultracook` is a thin orchestrator — it spawns sub-agents and reads the small handoff slug files they write. The preferred tools live inside each phase, not here. The orchestrator only needs:

| Need                              | Prefer                | Fallback                          |
|-----------------------------------|-----------------------|-----------------------------------|
| Spawning the per-phase worker     | `Agent()` / harness sub-agent primitive | none — without sub-agent spawn, the fresh-context property cannot be honoured |
| Reading the handoff slug          | `cheez-read` / host file read | host file read                    |
| Detecting existing handoffs       | host file glob / list | `cheez-search` `tilth_files` glob |

If the host harness does not expose a sub-agent primitive at all, `/ultracook` is the wrong skill — recommend `/cook --auto` instead, which uses the same flag semantics in the parent's own context.

## Rules

- Sub-agents are full peers, not diminutive workers. Do not downgrade the model, do not narrow `subagent_type`, do not restrict tools or MCP access.
- The chain is fixed: cook → press → age → cure → age → cure → age, all `--auto`, cure severity floor `medium+` (the `--stake` flag literal is preserved across callers). Do not invent extra phases or skip phases.
- Read each phase's handoff slug after the sub-agent returns. Do not infer success from the sub-agent's last line — read the file.
- Surface halts verbatim. Do not paraphrase, do not soften, do not "retry" a halted phase silently.
- At the terminal, push to an already-open PR via `/gh` (Rule 11); create a *new* PR only with `--open-pr`. Never push on a halt.
- Never wipe existing handoffs. Stop and tell the user to use `/cheese --continue` or `rm` by hand.
- Apply the shared voice kernel (lives at `skills/age/references/voice.md` in this repo): lead the final summary with what happened, flag residual risk as `certain | speculating | don't know`, do not manufacture follow-ups.
