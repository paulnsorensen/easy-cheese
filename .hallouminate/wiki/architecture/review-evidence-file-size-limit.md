# Review evidence file size limit

`easy-cheese-review` never gives ast-grep a file larger than `max_file_bytes` (default `MAX_FILE_BYTES`, 1 MiB).
The reviewed tree is untrusted input, and one generated or vendored file could cost unbounded ast-grep time and memory.
A whole-base import scan of this repository once wrote 9.8 MB of stdout for 632 code files.

## Result contract

`Evidence.to_json()["scan"]` always holds `skipped`: a list of `{tree, path, bytes}`, where `tree` is `head` or `base`.
An empty list means every file was scanned, so a consumer can tell "no hits" from "not scanned".
A skipped file has no hits, also when `scan.status` is `ok`.
`/age` reads this in `skills/age/references/fan-out.md`: review a skipped file by hand.

## Facts never become wrong

A skip makes a fact `unknown` with `{"reason": "file-too-large", "skipped": [...]}` only when the missing file can flip the value.
The rules live in `_compute_facts` and `_dependencies` in `packages/easy-cheese-review/src/easy_cheese_review/_evidence.py`.

- `tests` pairs file names and reads no file, so it stays known in every mode.
- `scope`: a missing import can only join groups, so `yes` becomes `unknown`.
- `compat`: a changed file skipped in either tree is not compared, so `no` becomes `unknown`.
- `dependencies`: a head skip turns `no` into `unknown`. A base skip turns a `yes` that rests only on `added_imports` into `unknown`; a manifest or lockfile change keeps `yes`.

## Base-tree exclusion

ast-grep 0.51.3 has no file-size flag, so the whole-base import scan (`imports(base, ["."])`) keeps the ast-grep directory walk and adds one `--globs '!/<path>'` per oversized file.
The leading `/` anchors the glob, and a backslash before each non-alphanumeric character other than `/._-` makes it literal (`_exclude_glob` in `_ast_grep.py`).
The package finds those files with its own `os.walk`, which skips hidden entries and links like ast-grep, and checks `SCAN_SUFFIXES`.
`SCAN_SUFFIXES` moved from `review_evidence.py` into the package so one set drives both base extraction and the walk.

## Known limits

- The walk reads no ignore file, so a library caller can see an ignored file in `skipped` and a conservative `unknown`.
  `age.pyz review-evidence` extracts only code blobs into a temporary base tree, so it has no ignore files.
- Each oversized base file adds two arguments to one ast-grep run. Thousands of them could pass the OS argument limit; the run then fails as `exec-error`, and `dependencies` becomes `unknown`.
- `_extract_base` streams `git cat-file --batch` one blob at a time, but it still reads each blob whole into memory and writes it to disk before the size check.
