# /wheypoint journey suite

These journeys drive `/skillz autoimprove` for `/wheypoint`.
Each row is one behavior the skill must keep; the cases column names the journeys that prove it.
The gate enforces four hard invariants: no Git commit, tag, or push; no `checkpoint` before a `validate`; no hand write to a note or projection; and no credential value in a checkpoint command or a new output file.

| ID | Behavior | Cases |
|---|---|---|
| `WHEY-1` | Reads the user turns with the turns command, and captures each one or states why it skips it. | `wheypoint-capture-1`, `wheypoint-capture-2`, `wheypoint-capture-3` |
| `WHEY-2` | Records constraints as directives with the verbatim quote and choices as decisions with a rationale. | `wheypoint-capture-1`, `wheypoint-route-1`, `wheypoint-refuse-2` |
| `WHEY-3` | Records a parked fork as a blocking question that names the options and the leaning, and reports the gated status. | `wheypoint-capture-2` |
| `WHEY-4` | Records how the user wants to be worked with as an operator preference, apart from task directives. | `wheypoint-capture-3` |
| `WHEY-5` | Sets next and artifact correctly: cook needs a spec path, affinage needs a PR reference, and the agent picks another move when the artifact is missing. | `wheypoint-capture-3`, `wheypoint-route-1`, `wheypoint-route-2`, `wheypoint-route-3` |
| `WHEY-6` | Validates before it checkpoints and fixes each refusal the runtime names. | `wheypoint-route-2`, `wheypoint-update-1` |
| `WHEY-7` | Updates an existing record by reading it first and writing against its revision, with transitions instead of deletion. | `wheypoint-update-1`, `wheypoint-update-2`, `wheypoint-refuse-3` |
| `WHEY-8` | Answers a status or resolve request with list, show, or resolve only, lists every ambiguous candidate, and writes nothing. | `wheypoint-read-1`, `wheypoint-read-2` |
| `WHEY-9` | Refuses to commit or push, to write a secret value, and to hand-edit a generated note or projection. | `wheypoint-refuse-1`, `wheypoint-refuse-2`, `wheypoint-refuse-3` |
| `WHEY-10` | Reports the durability the checkpoint returned and how to resume, even when no Git checkout exists. | `wheypoint-capture-1`, `wheypoint-refuse-1` |

## Out of scope offline

- Pinning a `path:line` to a short `HEAD` sha needs a Git checkout with history; the sandbox has none, so no journey covers the pin or the `unpinned-line-ref` warning.
- The `.cheese/notes/<slug>.md` mirror is written only inside a Git checkout; the sandbox reports `note_path: null`, so the final `Wheypoint dropped` link is checked only through the reported durability and resume commands.
- Cross-checkout resume through `/cheese --continue` and the `fork`, `export`, and `import` commands need a second project corpus and are not driven here.
