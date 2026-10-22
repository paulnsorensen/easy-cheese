# Session 4 (2026-09-27): wheypoint and milknado grounding

Scope: the wheypoint changes only.
Three questions: how wheypoint works, how the user wants it to work, how milknado works.
Goal: a seamless integration.
No source change, no commit.

## 1. Wheypoint as built

Kernel: `src/easy_cheese/shared/wheypoint/` (storage, canonical, records, checkpoint, commit, phase_commit, resolve, lint, lineage, projection, discovery, legacy, transcript).
CLI: `src/easy_cheese/cli/wheypoint/`, bundled as `skills/wheypoint/scripts/wheypoint.pyz`.
Verbs (10): checkpoint, handoff, lint, list, log, resolve, schema, show, turns, validate.

Record: `WheypointRecord` at `src/easy_cheese_schemas/contracts.py:3766-3808`.
Revision: `WheypointRevision` at `contracts.py:3928-3975`; delta at `contracts.py:3866-3925`.
Entries: question, decision, directive, blocker, each with a state and an optional `superseded_by`.
A question or blocker with `blocks_continuation: true` derives `status: gated` (`resolve.py:573-577`).
Status is derived, never authored (`contracts.py:3407,3819-3821`).

Store: `$XDG_DATA_HOME/cheese/<project_key>/work/<work_id>/` with `record.json`, `revisions/N-*.json`, `projections/N-*.md`.
Writes take `fcntl.flock` and promote atomically (`storage.py:139-146,245-257,407-465`).
The projection mirrors to `.cheese/notes/<slug>.md` and is never the authority.
No SQLite anywhere.
`project_key` comes from `EASY_CHEESE_PROJECT`, then the git remote `owner/repo`, then the directory name (`shared/paths.py:233`).
A foreign checkout gates resolution (`resolve.py:184-226,436-472`).

Links: `ArtifactLink{path, digest, revision_id, covers_entry_ids}` is a bare path pin.
`ArtifactRef{artifact_id, role, uri, digest, size_bytes, media_type, schema_uri}` exists at `contracts.py:598-606` and backs `HandoffPointer`, but the record does not use it.
There is no typed edge and no URI scheme in the record.

Writers: cook, press, age, cure, plate, and affinage commit their phase handoff as a wheypoint revision through `phase_commit.commit_phase_revision()` (`phase_commit.py:365-423`).
A phase handoff and a wheypoint revision are the same record type.

Milknado: zero wiring in `src/` or `skills/wheypoint/`.
The only mentions are a fan-pathway test fixture and AGENTS.md.

## 2. Milknado as built

Source of truth: origin/main `e841994` (2026-09-27).
The local checkout `/home/paul/Dev/milknado` is 24 commits behind (last `5d5ef97`, 2026-09-08).
The plugin runs `uvx --from git+https://github.com/paulnsorensen/milknado@main milknado-mcp`, so the installed tools track origin/main.
This session fetched origin but did not pull.

Store: SQLite at `.milknado/milknado.db`, WAL mode, two concurrent writers (detached runner and MCP server).
Tables: nodes, edges, file_ownership, plan_state, batch_plans, runs, run_messages, goal_claims, github_bind_attempts, node_reviews (`domains/graph/_persistence.py:113-333`).
Origin/main adds goal review admission (#450), follow-up provenance (#450), execution snapshots (#447), snapshot receipts, session persistence, and durable worker receipts (#441).

Node: `MikadoNode` at `domains/common/types.py:58-95`.
Fields: id, description, status, parent_id, worktree_path, branch_name, run_id, pid, created_at, completed_at, dispatched_at, oversized, batch_index, completion_duration_seconds, kind, flavor, goal_run_id, wiki_ref, github_ref, artifact_path, archived_at.
Kinds: roadmap, goal, task.
Flavors on origin/main: implement, spec, spike, prototype, research, review, plate, runner.
Node id is `INTEGER PRIMARY KEY AUTOINCREMENT` and is not stable across export and import.
`wiki_ref` is a deterministic uuid5 with a unique partial index, set only for imported roadmap and goal nodes.
`github_ref` has a unique partial index.
`artifact_path` is an opaque repo-relative markdown path with no uniqueness and no existence check (ADR organic-tasks-backbone-002).

Coupling today: file-format only.
`docs/adr/adversarial-review-loops-003.md:7` states no runtime coupling to easy-cheese.
`docs/adoption-contract.md:174-180` documents the wheypoint convention: put the projection path `.cheese/notes/<slug>.md` in `artifact_path` on the GOAL, and a resuming session reads it before `milknado_todo_next`.
Milknado imports no easy-cheese package.
Planner interchange is the `milknado.plan.v2` manifest consumed by `plan_apply`.

Goal review admission: a top-level goal change needs one durable human decision before execution continues.
Admission checks run at every execution boundary.
This is the same primitive as a wheypoint gated question.

## 3. What the user wants

Directives on the record: durable, linkable, pluggable into milknado; consolidate specs, ADRs, research, and wheypoints; easy-cheese schemas for spec, curd plan, and execution/eval; keep the pyz; export shareable schemas; use code to limit nondeterminism and token cost.
Live directives this session: focus on the wheypoint changes; the integration must be seamless.

Decided 2026-08-28 (work `graph-flow-schemas`): Shape B.
Milknado imports the `easy-cheese-schemas` package at runtime.
Zero coupling is the status quo, not the goal.
Shape B is unexecuted, and that record's own next move is `mold`.

Seam ADRs 001 to 006 are accepted.
They define the CurdPlan executor seam with `source_plan_ref` and `source_curd_ref`, make `ArtifactRef` canonical (ADR-002), and sequence easy-cheese proof before milknado adoption (ADR-006).
None names the wheypoint link.
`wheypoint_ref`, `work-edge`, and the ArtifactLink promotion are agent proposals only.

## 4. Findings that change the design

1. The documented convention points at the wrong thing.
   `artifact_path = .cheese/notes/<slug>.md` names the non-authoritative projection by a checkout-relative path.
   Milknado workers run in per-node worktrees that may not contain that mirror.
   The ref must name `<project_key>/<work_id>`, which `wheypoint resolve` finds from any checkout.
2. Milknado has no stable node key for every node.
   A wheypoint cannot hold a durable pointer to an autoincrement id.
   Either every node gets a uuid5 key like `wiki_ref`, or the pointer lives only on the milknado side.
3. Idempotent attach needs a unique partial index.
   `artifact_path` has none; a `wheypoint_ref` column on the `wiki_ref` precedent does.
4. Both systems now own a human decision gate.
   Seamless means one decision recorded once and visible in both: a wheypoint gated question maps to a pending goal review, a resolve transition maps to an accepted review, a blocker maps to a blocked node, and a checkpoint maps to a snapshot receipt.
5. Milknado ADR-003 (format-only coupling) contradicts Shape B.
   Executing Shape B requires amending that ADR.
6. `ArtifactLink` cannot pin a durable artifact.
   The checkpoint runtime refused this report's absolute XDG path with `commit-refused: add_artifact_links names a path this host cannot digest`.
   Links resolve only repo-relative, so the durable corpus, a milknado node, and a wiki page are all unlinkable today.
   This is the concrete case for a URI-bearing `ArtifactRef` on the record.

## 5. The weighing on the gating fork

Option A: shared schemas, separate stores, link by pointer.
Evidence: ADR-006 sequencing; the organic-tasks-backbone rule "DB owns graph and status, files own prose"; the two locking models (flock plus atomic promote against WAL with two writers).
Cost: milknado adds a stable node key and a `wheypoint_ref` index; the record adopts `ArtifactRef` with a URI; a cross-store query needs a join.

Option B: one store, engine bolted onto the record type.
Evidence: the 09-24 thread recommendation, unanswered.
Cost: mutable execution fields (status, run_id, pid, worktree_path, dispatched_at, batch_index) enter an append-only digest chain, so each status flip becomes a revision or the nothing-dropped proof weakens.
Milknado's new durable concepts (goal review, receipts, session persistence, about 2,000 lines since 09-08) need a new home.
Milknado's release cycle couples to the schema package.

Recommendation: Option A with the four additions in section 4.
The seamless part is the decision-gate mapping, not a store merge.

## 6. Evidence artifacts

- `.cheese/explore/wheypoint-as-built.md` (transient, this worktree)
- `.cheese/explore/milknado-as-built.md` (transient, this worktree; grounded on the stale checkout, corrected above)
- `/home/paul/Dev/milknado/docs/adoption-contract.md:174-180`
- `/home/paul/Dev/milknado/src/milknado/domains/common/types.py:58-95`
- `/home/paul/.local/share/cheese/paulnsorensen-easy-cheese/work/graph-flow-schemas/record.json`
