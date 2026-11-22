# easy-cheese-review

Review evidence for [easy-cheese](https://github.com/paulnsorensen/easy-cheese) reviewers (`/age`) and for affineur.
The package holds three parts:

- `easy_cheese_review.severity`: the `/age` severity rubric (base severity, contract and structural bumps, fix-cost-now buckets).
- `easy_cheese_review.rules`: an ast-grep rule pack for Python and TypeScript/JavaScript. Every rule carries `metadata: {dimension, base}`.
- `easy_cheese_review.scan` and `easy_cheese_review.facts`: a scan of changed files and four deterministic facts (`compat`, `dependencies`, `tests`, `scope`).

The package is not on PyPI yet, because no workflow publishes it.
Install it from a checkout of the repository:

```sh
pip install ./packages/easy-cheese-review
```

Requires Python 3.11 or newer and `easy-cheese-schemas>=4,<5`.
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

## Result

`Evidence.to_json()` returns this shape:

```json
{
  "scan": {"status": "ok", "skipped": [{"tree": "head", "path": "gen/big.py", "bytes": 4194304}]},
  "hits": [{"rule_id": "py-eval-exec", "dimension": "security", "base": "high", "path": "app.py", "line": 3, "end_line": 3, "message": "..."}],
  "facts": {"compat": {"value": "no", "detail": {"removed": []}}}
}
```

`scan.status` is `ok` or `failed:<reason>`.
`facts` holds one entry for each of `compat`, `dependencies`, `tests`, and `scope`; the example shows one.

## File size limit

No ast-grep run reads a file larger than `max_file_bytes` (default `MAX_FILE_BYTES`, 1 MiB).
`scan` and `facts` take `max_file_bytes` as a keyword argument.
The limit covers the changed files in `head` and `base`, and every file of the whole-base import scan.
`scan.skipped` lists each file left out, with its tree (`head` or `base`), path, and size in bytes.
The list is always present. When `scan.status` is `ok`, an empty list means every file was scanned.
A skipped file has no hits, also when its status is `ok`.

A skip makes a fact `unknown`. Its detail keeps the original keys and adds `"reason": "file-too-large"` and `"skipped": [...]`. It happens only when the missing file can change the value:

| Fact | Effect of a skipped file |
| --- | --- |
| `tests` | None. It pairs file names and reads no file. |
| `scope` | A missing import can only join groups, so `yes` becomes `unknown`; `no` stays. |
| `compat` | A changed file skipped in either tree is not compared, so `no` becomes `unknown`; `yes` stays. |
| `dependencies` | A skipped head file can hide a new import, so `no` becomes `unknown`. A skipped base file can hide a known import, so a `yes` that rests only on `added_imports` becomes `unknown`. A manifest or lockfile change keeps `yes`. |

The whole-base import scan excludes each oversized file by its exact path.
To find those files, the package walks `base`, skipping hidden entries and links like ast-grep does, and checks the suffixes in `SCAN_SUFFIXES`.
The walk does not read ignore files, so it can report an ignored file that ast-grep would not read anyway.

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
