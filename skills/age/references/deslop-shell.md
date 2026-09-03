# Shell / Bash De-slop Catalog

This catalog provides per-language evidence for the `age` `deslop` dimension. Each pattern identifies a shell-specific AI tell for review. Most patterns map to a ShellCheck code. Each code supplies a citable rule name for a finding. Use this catalog with `dimensions.md`'s `deslop` rubric. This catalog supplies the "Look for" detail. It does not define a separate severity scale.

## 1. Unquoted variables

This pattern causes the number-one shell bug. Unquoted variables break on spaces, globs, and empty values.
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

Quote every variable expansion: `"$var"`, `"${array[@]}"`, `"$(command)"`. The `--` stops option parsing and protects against filenames that start with `-`.

## 2. Missing or incomplete `set -euo pipefail`

AI scripts either omit strict mode or use only `set -e`, without `-u` and `-o pipefail`. Both patterns are dangerous.

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

- The `-e` option makes the shell exit after an error.
- The `-u` option reports undefined variables and catches typos such as `$UESR` instead of `$USER`.
- The `-o pipefail` option makes a pipeline fail when any command fails, not only the last command.

Use all three flags together. `set -e` alone is a half-measure. A script can silently swallow a left-side failure when it pipes through `jq`/`yq`/`grep`.

### Strict mode is not a cure-all

`set -e` has sharp edges (BashFAQ/105). Do not assume it catches every failure:

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

The `ls` output is not machine-readable. Filenames with spaces, newlines, or special characters break parsers.

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

Backticks do not nest and are harder to read.

```bash
# SLOP
result=`command`
nested=`echo \`date\``

# CLEAN
result=$(command)
nested=$(echo "$(date)")
```

## 6. `[ ]` instead of `[[ ]]`

`[[ ]]` is safer because it prevents word splitting, supports regular expressions, and avoids quoting surprises.

```bash
# SLOP
if [ $var = "value" ]; then
if [ -z $maybe_empty ]; then

# CLEAN
if [[ "$var" == "value" ]]; then
if [[ -z "${maybe_empty:-}" ]]; then
```

## 7. Hardcoded paths

AI writes absolute paths or assumes `CWD`.

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

Write errors to stderr, not stdout.

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

ShellCheck rule `SC2181` flags this pattern.

## 11. `cd` without a fallback

This pattern has the highest consequence. A failed `cd` caused by a typo or permission issue lets every following command, including `rm -rf`, run in the wrong directory.

```bash
# SLOP
cd "$build_dir"
rm -rf ./*

# CLEAN
cd "$build_dir" || exit 1
rm -rf ./*
```

ShellCheck rule `SC2164` flags this pattern.

## 12. Iterating command output with `for`

`for x in $(cmd)` splits output on whitespace instead of lines. This behavior breaks on spaces and globs.

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

ShellCheck rule `SC2044` covers find loops. ShellCheck rule `SC2046` covers unquoted `$(...)` generally.

## 13. Piping into `while read` and losing variables

Each side of a pipe runs in a subshell. Assignments inside the loop disappear when the subshell exits.

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

`echo` flags behave differently in the Bash builtin and `/bin/echo`. These flags are not POSIX-portable.

```bash
# SLOP
echo -e "line1\nline2"
echo -n "no newline"

# CLEAN
printf '%s\n' "line1" "line2"
printf '%s' "no newline"
```

## 15. `expr`, `let`, `$[ ]` arithmetic

These forms start external processes or use deprecated syntax for operations the shell performs natively.

```bash
# SLOP
i=$(expr $i + 1)
let i=i+1
result=$[ a + b ]

# CLEAN
(( i += 1 ))
result=$(( a + b ))
```

The Google Shell Style Guide says to always use `(( ))` or `$(( ))` for arithmetic.

## 16. Bare `$@` / `$*` for argument forwarding

Unquoted `$@` and `$*` split on internal spaces and drop empty arguments.

```bash
# SLOP
my_func $@

# CLEAN
my_func "$@"
```

## Sources

- The ShellCheck wiki (shellcheck.net/wiki/SCxxxx) provides canonical slop-to-fix rationale for each code.
- Greg's Wiki, including BashPitfalls and BashFAQ/105, provides calibration guidance for `set -e`.
- The Google Shell Style Guide covers arithmetic, quoting, loop idioms, and when not to use Bash.
