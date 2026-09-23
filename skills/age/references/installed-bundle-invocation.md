# Installed bundle invocation

Use this Bash or zsh function when the checkout lacks the `/age` archive.
It resolves the installed skill by exact name, rejects zero or multiple matches, and rejects a missing archive before execution.

```bash
run_age_bundle() {
    local host="$1" skill_dir archive
    shift
    skill_dir="$(gh skill list --agent "$host" --scope user --json path,skillName \
        --jq '.[] | select(.skillName=="age") | .path')" || return 2
    if [[ -z "$skill_dir" || "$skill_dir" == *$'\n'* ]]; then
        printf 'error: age skill path is missing or ambiguous\n' >&2
        return 2
    fi
    archive="$skill_dir/scripts/age.pyz"
    if [[ ! -f "$archive" ]]; then
        printf 'error: age archive is missing: %s\n' "$archive" >&2
        return 2
    fi
    python3 "$archive" "$@"
}

run_age_bundle "$HOST" severity compute --dimension security --base low \
    --location module --fix-cost-later contained
run_age_bundle "$HOST" severity compute --dimension correctness --base high \
    --location contract --fix-cost-later spreading
```

Keep the archive and each argument separate. Pass repeated cases as separate calls.
Do not evaluate one scalar command string or split an unquoted case specification.
