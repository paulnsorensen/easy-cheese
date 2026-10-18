# Handoff branch menus

Read this after the user selects Cook. A saved draft alone renders no Cook command. The `curd-count` digest guides sizing; it does not grant execution authority.

- A `ready` finalization result carries `request_id`, `spec_ref`, `planner_result_ref`, `plan_ref`, exact `coverage`, and a retained `result_path`.
- A `saved-not-ready` result carries unmet requirements and holds, not runnable bound inputs. Show each item. Do not dispatch bound execution. A separate clear standalone task may use `/cook --spec "$SPEC"` only when Cook's fast-path conditions hold and the user explicitly requests that route.
- For a ready bound result, auto choices use the printed `command` (`/cook --auto --result "$RESULT_PATH"`); manual choices use `/cook --result "$RESULT_PATH"`. For standalone work, use `/cook --auto --spec "$SPEC"` or `/cook --spec "$SPEC"`. The host passes the ready refs to `execute_bound_plan` and validates them before writer dispatch.

After explicit Cook selection, render the branch selected by the sizing digest's `mode`:

**Decomposable specs (`decomposable: true`, `candidate_curds ≥ 2`, `mode: parallel`):**

- **Run the full pipeline (parallel fan-out when disjoint, else linear)** *(recommended)* — use the auto command above. Cook uses plan curds to select parallel or linear execution; `/plate` publishes the selected ordinary or stacked layout.
- **Implement manually, one phase at a time** — use the manual command above.
- **Stop** — dispatch none; leave the spec for later.

**Non-decomposable, high-blast-radius specs (`decomposable: false`, verdict `high` only, `mode: linear`):**

- **Run the full pipeline in fresh-context isolation** *(recommended)* — use the auto command. Behavior work continues `cook → press → age → cure → age → cure → age`; non-behavior work skips Press and continues `cook → age → cure → age → cure → age`.
- **Implement manually, one phase at a time** — use the manual command.
- **Compact and resume by hand** — dispatch none; clear context, then use the manual command. `/cheese --continue` scans phase handoff slugs, so a fresh spec must be resumed through its explicit path.
- **Stop** — dispatch none; leave the spec for later.

**Non-decomposable, low- or medium-blast-radius specs (`decomposable: false`, verdict `low` or `medium`, `mode: null`):**

- **Implement the spec** *(recommended)* — use the manual command.
- **Implement and auto-review** — use the auto command. Opening or updating a PR remains `/plate`'s explicit step.
- **Research more first** — `/briesearch`.
- **Stop** — dispatch none; leave the spec for later.

`mode: parallel|linear` selects fresh-context Cook execution; `mode: null` selects the smaller in-session path. This digest mode is not a Mold-to-Cook execution gate. The user must still opt into `--auto`.
