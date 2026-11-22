# easy-cheese-review

Review evidence for [easy-cheese](https://github.com/paulnsorensen/easy-cheese) reviewers (`/age`) and for affineur.
The package holds three parts:

- `easy_cheese_review.severity`: the `/age` severity rubric (base severity, contract and structural bumps, fix-cost-now buckets).
- `easy_cheese_review.rules`: an ast-grep rule pack for Python and TypeScript/JavaScript. Every rule carries `metadata: {dimension, base}`.
- `easy_cheese_review.scan` and `easy_cheese_review.facts`: a scan of changed files and four deterministic facts (`compat`, `dependencies`, `tests`, `scope`).

Install it from PyPI:

```sh
pip install easy-cheese-review
```

Requires Python 3.11 or newer and `easy-cheese-schemas>=4.0.1,<5`.
The [ast-grep](https://ast-grep.github.io) binary is optional.
When `ast-grep` is not on `PATH`, `scan` returns `status: failed:ast-grep-missing` and no hits.
The `tests` fact needs no ast-grep and stays known; `compat`, `dependencies`, and `scope` are `unknown` with the reason.

## Usage

```python
from pathlib import Path

from easy_cheese_review import hunks_from_diff, scan

diff = Path("review_input/diff.patch").read_bytes().decode("utf-8", "surrogateescape")
evidence = scan(
    Path("head"),
    ["src/app.py", "tests/test_app.py"],
    base=Path("base"),
    hunks=hunks_from_diff(diff),
)
print(evidence.to_json())
```

`scan` runs the rules only through `ast-grep scan -c <packaged sgconfig.yml>`.
It never reads an `sgconfig.yml` or a rule file from the scanned tree.
Hits are evidence for a reviewer to confirm or reject. They are not findings by themselves.

`hunks` keeps only the hits on changed lines.
A changed path with no `hunks` entry counts as changed in full, so `scan` keeps each of its hits.
`hunks_from_diff` maps a deletion-only hunk to the lines on each side of the cut.
It ends a diff line only at a line feed.
Read the diff as bytes, as the example does: text mode turns a lone carriage return into a line break.

## Known gaps

- The TypeScript rules run on `.ts`, `.js`, `.mjs`, and `.cjs` files. `.tsx` and `.jsx` files get no rule hits yet.
- `ast-grep outline` 0.51.2 omits `export default <expression>` and `export type { ... }`, so `compat` does not see their removal.
- The `tests` fact pairs files by name, so a test for `accounts/user.py` also covers `billing/user.py`.
- ast-grep 0.51 stops when a path argument is not valid UTF-8. A changed code file with such a name fails the scan: `status: failed:exit-101` and no hits.

## Facts

Each fact is `yes`, `no`, or `unknown`, with a `detail` object.

| Fact | `yes` means |
| --- | --- |
| `compat` | An exported name at base is gone at head (`ast-grep outline --items exports`). |
| `dependencies` | A manifest or lockfile changed, or a changed file imports a new third-party module (the packaged `queries/imports.yml` query, run through `ast-grep scan --inline-rules`). |
| `tests` | A changed source file has no matching changed test file. |
| `scope` | The changed code files form two or more groups with no import between them. |

## Rule tests

```sh
ast-grep test -c src/easy_cheese_review/rules/sgconfig.yml
```
