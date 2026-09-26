# Early curds and composed specs

Read this when a concrete curd appears before the parent design is complete. This is an in-dialogue Mold path, not the leverage-free Quick path.

## Boundary

Mold may save a draft parent spec and a draft mini-spec without a separate extraction approval. Saving does not authorize Cook. No coder, worktree writer, `/cook` command, or automatic chain starts until the user explicitly selects that curd and a Cook route. Silence, a general approval of the idea, `--auto`, and a saved spec are not execution consent.

A curd is ready to mint only when its scope, acceptance checks, test applicability, dependencies, and non-goals are concrete. Every consequential decision used by that curd must be settled. Open parent forks may remain only when they cannot change the curd's contract. If a parent fork can change it, keep shaping instead of minting.

## Composition

Resolve the parent and child paths with `mold.pyz artifact-path specs <slug>`. Use a distinct child slug. The child uses `source: mold-curd-mini-spec`, `status: draft`, the mini-spec schema in `mini-spec-mode.md`, and a required `## Parent` section:

```markdown
## Parent
- Spec: <parent slug>
- Goals: G-1, G-2
- Depends on: <child slugs or none>
- Frozen decisions: F-1, F-2
```

The parent `## Curds` section lists each child slug, its resolved spec path, covered `G-n` clauses, dependencies, selected route, and state: `draft | cooking | cooked | integrated | superseded`. Keep unresolved parent goals and forks in the parent. Do not claim that a cooked child completes the parent. Do not copy a child's acceptance text into the parent; the child is the contract for that slice. Validate each child with `mold.pyz validate-spec --strict`, then read it back. A failed check leaves the child unminted.

A changed child contract gets a new revision and a new execution decision. Do not overwrite an already cooking or cooked child. Recheck parent decisions and file overlap before integrating a Cook result. A conflicting result returns to Mold for reconciliation; it does not silently rewrite either contract.

## Cook selection

Show the child contract, dependencies, changed files or intended footprint, and remaining parent work. Ask one route question through [`ask-user-question.md`](../../cheese/references/ask-user-question.md) only when the user wants Cook:

- **Cook here in isolation:** dispatch the canonical Mold-to-Cook pointer to one isolated coder or worktree. Keep Mold's parent dialogue state with the orchestrator.
- **Cook in another worktree:** give the user a command that names the child spec and its revision or digest. For local worktrees with a shared corpus, run `python3 skills/mold/scripts/mold.pyz artifact-path specs <child-slug>` and show `/cook --spec <absolute-path-printed-by-resolver>`. For a destination without that corpus, supply the complete validated spec as a portable file and show `/cook --spec <copied-spec-path>`. The destination must bind the user's Cook request to its own exact proposal. Never give a bare slug or a local-only path as if it worked in a cloud worktree.
- **Keep shaping:** dispatch none. The child remains a validated draft.

A direct `cook it` or `cook this` selection is execution consent only when the displayed child and route are unambiguous. The approval envelope binds the scope or plan, not the dispatch route. Record the selected route beside the child in the parent `## Curds` section. Execute only that route. A route change needs a new user selection, even when the scope and plan stay unchanged.

For **Cook here in isolation**, mark only that child's lifecycle `approved`. Follow [`curdle.md`](curdle.md) § Finalization for the approve-then-finalize sequence. Bind the literal response with `mold.pyz approve --kind scope --curd-id <curd-id>`. Then run `mold.pyz finalize --mode light`, passing `--taste-result` and `--ledger`. Dispatch only a `ready` consumer-valid pointer. If finalization returns `saved-not-ready`, show its holds. Do not dispatch when a hold remains. A new plan or changed scope needs a new Cook selection.

For **Cook in another worktree**, provide the validated spec and command without starting local Cook or publishing a local execution pointer. The destination binds the user's Cook request to its own proposal before execution. `--auto` may chain phases after Cook begins; it never starts Cook by itself.

Continue shaping the parent after the isolated dispatch or command handoff. Record the child's result and any new constraints in the parent ledger. The user chooses when to Cook another child or the remaining parent scope.
