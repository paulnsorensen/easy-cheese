# Shell / Bash De-slop Catalog

This catalog gives per-language evidence for the `age` `deslop` dimension.
Each pattern names a shell-specific AI signature for review.
Most patterns map to a ShellCheck code, which gives a citable rule name for a finding.
Use this catalog with the `deslop` rubric in `dimensions.md`.
This catalog supplies the detail. It defines no separate severity scale.

## Detect the shell first

Read the shebang line and the file extension before you grade a pattern.
These rules are Bash rules unless a pattern says otherwise.

| Shell | Rules that apply |
| --- | --- |
| `#!/bin/bash`, `#!/usr/bin/env bash`, `.bash` | Every rule in this catalog |
| `#!/bin/sh`, `.sh` with no shebang, a POSIX target | Quoting and `cd` rules only. `[[ ... ]]` is a syntax error in POSIX shell. Use `[ ... ]` there |
| A file that another script sources | See the sourced-file rules under each pattern |

Do not raise a `[[ ... ]]` finding against a POSIX script.
Do not raise a strict-mode finding against a sourced file.

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

Use all three flags together in an executable script.
`set -e` alone is a half-measure. A script can silently swallow a left-side failure when it pipes through `jq`, `yq`, or `grep`.

Do not set strict mode in a file that another script sources.
The options stay set in the calling shell after the source returns.
An interactive shell can then exit on the next unset variable.
Set the options inside each function of a sourced file instead.

### Strict mode does not catch every failure

`set -e` has documented gaps (BashFAQ/105). Do not assume that it catches every failure:

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

# CLEAN — find for a recursive search
find . -name '*.txt' -print0 | while IFS= read -r -d '' file; do
    process "$file"
done

# CLEAN — fd only when the project already declares it as a dependency
fd -e txt -x process {}
```

Prefer the standard command. Use `fd` only when the project declares it.

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

In Bash, `[[ ]]` is safer. It prevents word splitting, supports regular expressions, and avoids quoting surprises.
`[[ ]]` is a Bash keyword. It fails in POSIX shell with `[[: not found`.
Grade this pattern only when the shebang names Bash.

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

# CLEAN — in an executable script
cd "$build_dir" || exit 1
rm -rf ./*

# CLEAN — in a function of a sourced file
cd "$build_dir" || return 1
rm -rf ./*
```

Use `exit` only in an executable script.
`exit` inside a sourced file terminates the calling shell.
Use `return` in every function of a sourced file.
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

ShellCheck rule `SC2044` covers a `find` loop.
ShellCheck rule `SC2046` covers an unquoted `$(...)` expansion.

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
