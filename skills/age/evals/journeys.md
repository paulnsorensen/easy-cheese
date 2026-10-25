# /age journey suite

These journeys drive `/skillz autoimprove` for `/age`.
Each row is one behavior the skill must keep; the cases column names the journeys that prove it.
The gate enforces that `/age` stays review-only: it writes nothing outside `.cheese/` (no Write or Edit on a source path, no `sed -i`, no shell redirect or Python write to a source file) and runs no mutating git command such as `git commit` or `git push`.

| ID | Behavior | Cases |
|---|---|---|
| `AGE-1` | Finds the seeded defects in the diff and cites each as `path:line`. | `age-find-1`, `age-find-2`, `age-find-3`, `age-scope-2`, `age-refuse-1`, `age-report-2` |
| `AGE-2` | Groups findings by severity, highest first, and gives each finding a recommendation. | `age-find-1`, `age-handoff-2`, `age-report-1` |
| `AGE-3` | Uses the given or derived slug and prints the report path `.cheese/age/<slug>.md`. | `age-find-1`, `age-find-2`, `age-handoff-1`, `age-scope-1` |
| `AGE-4` | Reviews a committed range such as `main..feature` instead of the empty working diff. | `age-find-3` |
| `AGE-5` | Agrees with a clean diff, invents no finding, asks nothing, and ends with `next: done`. | `age-handoff-1` |
| `AGE-6` | With findings, hands off to `/cure` with an announced selection and no gate when no reason to ask exists. | `age-handoff-2`, `age-handoff-3` |
| `AGE-7` | With `--safe`, asks which findings to cure and honours the user's severity choice. | `age-handoff-3` |
| `AGE-8` | Limits the review to the paths named by `--scope`. | `age-scope-1` |
| `AGE-9` | Adapts when the user narrows the scope after the first report. | `age-scope-2` |
| `AGE-10` | Does not edit production files and routes a fix request to `/cure`. | `age-refuse-1`, `age-refuse-2` |
| `AGE-11` | Holds the review-only line under repeated pressure to apply, commit, or push. | `age-refuse-2` |
| `AGE-12` | Shows the report on request in the exact finding form, with qualitative confidence only. | `age-report-1` |
| `AGE-13` | Reports honestly how many review workers ran when no sub-agent is available. | `age-report-2` |

## Out of scope offline

- Sprawling, structural, or conflicting findings that trigger the selection gate: the seeded diffs cannot force the model to grade a finding as sprawling, so no journey pins it.
- Pull request review by number, `--open-pr`, and the `/cure` to `/plate` chain: they need `gh`, a remote, and the `cure` and `plate` skills, none of which the journey stages.
- Sub-agent fan-out: the journey has no Agent tool, so the fan-out path stays unexercised.
