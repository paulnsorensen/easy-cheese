# Shell / Bash De-slop Catalog

Per-language evidence for the `age` `deslop` dimension. Each pattern is a shell-specific AI tell to look for during review; most map to a ShellCheck code, giving a citable rule name to attach to a finding. Use alongside `dimensions.md`'s `deslop` rubric — this is the "Look for" detail, not a separate severity scale.

## 1. Unquoted variables

The #1 shell bug. Breaks on spaces, globs, and empty values.

```bash
# SLOP
for file in $files; do
    rm $file
done

# CLEAN
for file in "${files[@]}"; do
    rm -- "$file"
done
```

Quote every variable expansion: `"$var"`, `"${array[@]}"`, `"$(command)"`.
The `--` stops option parsing (protects against filenames starting with `-`).

## 2. Missing or incomplete `set -euo pipefail`

AI scripts either omit strict mode entirely or use partial `set -e` without
`-u` and `-o pipefail`. Both are dangerous.

```bash
# SLOP — no strict mode
#!/bin/bash
cd /some/directory    # Might fail silently
rm -rf build/         # Now you're deleting in the wrong place

# SLOP — partial strict mode (common AI output)
#!/bin/bash
set -e
yq '.items[]' file.yaml | while read -r item; do  # yq failure silently ignored
    process "$item"
done

# CLEAN
#!/bin/bash
set -euo pipefail
cd /some/directory
rm -rf build/
```

- `-e`: Exit on error
- `-u`: Error on undefined variables (catches typos like `$UESR` instead of `$USER`)
- `-o pipefail`: Pipeline fails if any command fails (not just the last)

All three flags together. `set -e` alone is a half-measure — especially
dangerous in scripts that pipe through `jq`/`yq`/`grep` where a failure
on the left side is silently swallowed.

### Strict mode is not a cure-all

`set -e` has sharp edges (BashFAQ/105) — don't assume it catches everything:

```bash
# MASKED — `local`'s own success hides the command's failure
local output=$(failing_cmd)      # -e does NOT fire

# CLEAN — declare and assign in two steps
local output
output=$(failing_cmd)            # -e fires here

# MASKED — -e is disabled inside a function used as a conditional
if my_func; then ...             # failures inside my_func won't exit
```

## 3. Parsing `ls` output

`ls` output is not machine-readable. Filenames with spaces, newlines,
or special characters break everything.

```bash
# SLOP
for file in $(ls *.txt); do
    process "$file"
done

# CLEAN — glob directly
for file in *.txt; do
    [[ -f "$file" ]] && process "$file"
done

# CLEAN — fd for complex searches
fd -e txt -x process {}
```

## 4. Useless use of `cat`

```bash
# SLOP
cat file.txt | grep "pattern"
cat file.txt | wc -l

# CLEAN
grep "pattern" file.txt
wc -l < file.txt
```

## 5. Backticks instead of `$()`

Backticks don't nest and are harder to read.

```bash
# SLOP
result=`command`
nested=`echo \`date\``

# CLEAN
result=$(command)
nested=$(echo "$(date)")
```

## 6. `[ ]` instead of `[[ ]]`

`[[ ]]` is safer: no word splitting, supports regex, no quoting surprises.

```bash
# SLOP
if [ $var = "value" ]; then
if [ -z $maybe_empty ]; then

# CLEAN
if [[ "$var" == "value" ]]; then
if [[ -z "${maybe_empty:-}" ]]; then
```

## 7. Hardcoded paths

AI writes absolute paths or assumes CWD.

```bash
# SLOP
source /home/user/project/lib/utils.sh
config_file=./config.yaml

# CLEAN
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/lib/utils.sh"
config_file="${SCRIPT_DIR}/config.yaml"
```

## 8. Not using `readonly` for constants

```bash
# SLOP
MAX_RETRIES=3
BASE_URL="https://api.example.com"

# CLEAN
readonly MAX_RETRIES=3
readonly BASE_URL="https://api.example.com"
```

## 9. Using `echo` for error messages

Errors go to stderr, not stdout.

```bash
# SLOP
echo "Error: file not found"
exit 1

# CLEAN
echo >&2 "Error: file not found"
exit 1

# Or with a helper
die() { echo >&2 "$@"; exit 1; }
die "file not found"
```

## 10. Checking `$?` instead of the command

```bash
# SLOP
some_command
if [ $? -eq 0 ]; then
    echo "ok"
fi

# CLEAN
if some_command; then
    echo "ok"
fi

# CLEAN — error path
if ! some_command; then
    die "some_command failed"
fi
```

ShellCheck: SC2181.

## 11. `cd` without a fallback

The highest-consequence tell: a failed `cd` (typo, permissions) lets every
following command — including `rm -rf` — run in the wrong directory.

```bash
# SLOP
cd "$build_dir"
rm -rf ./*

# CLEAN
cd "$build_dir" || exit 1
rm -rf ./*
```

ShellCheck: SC2164.

## 12. Iterating command output with `for`

`for x in $(cmd)` splits on whitespace, not lines — breaks on spaces and globs.

```bash
# SLOP
for f in $(find . -name '*.log'); do
    process "$f"
done

# CLEAN — NUL-delimited for filenames
find . -name '*.log' -print0 | while IFS= read -r -d '' f; do
    process "$f"
done

# CLEAN — line-oriented command output
readarray -t lines < <(cmd)
```

ShellCheck: SC2044 (find loops), SC2046 (unquoted `$(...)` generally).

## 13. Piping into `while read` and losing variables

Each side of a pipe runs in a subshell — assignments inside the loop vanish.

```bash
# SLOP — prints 0
count=0
cat file | while read -r line; do
    count=$((count + 1))
done
echo "$count"

# CLEAN — redirect (or process-substitute); no subshell
count=0
while read -r line; do
    count=$((count + 1))
done < file
```

## 14. `echo -e` / `echo -n`

`echo`'s flag behavior differs between the bash builtin and `/bin/echo` and
isn't POSIX-portable.

```bash
# SLOP
echo -e "line1\nline2"
echo -n "no newline"

# CLEAN
printf '%s\n' "line1" "line2"
printf '%s' "no newline"
```

## 15. `expr`, `let`, `$[ ]` arithmetic

External processes and deprecated syntax for what the shell does natively.

```bash
# SLOP
i=$(expr $i + 1)
let i=i+1
result=$[ a + b ]

# CLEAN
(( i += 1 ))
result=$(( a + b ))
```

Google Shell Style Guide: always `(( ))` / `$(( ))`.

## 16. Bare `$@` / `$*` for argument forwarding

Unquoted, both split on internal spaces and drop empty arguments.

```bash
# SLOP
my_func $@

# CLEAN
my_func "$@"
```

## Sources

- ShellCheck wiki (shellcheck.net/wiki/SCxxxx) — canonical slop→fix rationale per code
- Greg's Wiki: BashPitfalls + BashFAQ/105 — the `set -e` calibration source
- Google Shell Style Guide — arithmetic, quoting, loop idioms, when not to use bash at all
