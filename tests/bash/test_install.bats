#!/usr/bin/env bats
#
# Tests for scripts/install.sh.
#
# The script is sourced (the BASH_SOURCE != $0 guard skips main on source)
# so each test can call individual functions with controlled stubs.

setup() {
    REPO_ROOT="$(cd "$(dirname "$BATS_TEST_FILENAME")/../.." && pwd)"
    INSTALL_SH="$REPO_ROOT/scripts/install.sh"
    STUB_BIN="$BATS_TEST_TMPDIR/bin"
    STUB_LOG="$BATS_TEST_TMPDIR/calls.log"
    mkdir -p "$STUB_BIN"
    : > "$STUB_LOG"
    export STUB_LOG
    PATH_ORIG="$PATH"
    # Use a sparse PATH so the only commands available are real /usr/bin
    # essentials plus whatever stubs each test adds.
    PATH="$STUB_BIN:/usr/bin:/bin"
    # shellcheck disable=SC1090
    source "$INSTALL_SH"
}

teardown() {
    PATH="$PATH_ORIG"
}

# Drop a stub binary into $STUB_BIN that records its argv to $STUB_LOG.
make_stub() {
    local name="$1" exit_code="${2:-0}"
    cat > "$STUB_BIN/$name" <<STUB
#!/usr/bin/env bash
echo "$name \$*" >> "$STUB_LOG"
exit $exit_code
STUB
    chmod +x "$STUB_BIN/$name"
}

# Count the embedded skills in $EC_FALLBACK_SKILLS without spawning subshells.
count_skills() {
    set -- $EC_FALLBACK_SKILLS
    echo $#
}

# -- ec_tool_binary -----------------------------------------------------------

@test "ec_tool_binary maps formula names to binaries" {
    [[ "$(ec_tool_binary ripgrep)" == "rg" ]]
    [[ "$(ec_tool_binary ast-grep)" == "sg" ]]
    [[ "$(ec_tool_binary git-delta)" == "delta" ]]
    [[ "$(ec_tool_binary jq)" == "jq" ]]
    [[ "$(ec_tool_binary fd)" == "fd" ]]
    [[ "$(ec_tool_binary just)" == "just" ]]
    [[ "$(ec_tool_binary mergiraf)" == "mergiraf" ]]
    [[ "$(ec_tool_binary tilth)" == "tilth" ]]
    [[ "$(ec_tool_binary gh)" == "gh" ]]
}

# -- ec_validate_selection ----------------------------------------------------

@test "ec_validate_selection accepts subset of allowed list" {
    run ec_validate_selection "ripgrep,jq" "$EC_KNOWN_TOOLS"
    [ "$status" -eq 0 ]
}

@test "ec_validate_selection rejects unknown token" {
    run ec_validate_selection "ripgrep,bogus" "$EC_KNOWN_TOOLS"
    [ "$status" -ne 0 ]
    [[ "$output" == *"Unknown selection: bogus"* ]]
}

@test "ec_validate_selection accepts the special 'none' MCP token" {
    run ec_validate_selection "none" "tilth context7 tavily code-review-graph none"
    [ "$status" -eq 0 ]
}

# -- ec_parse_args ------------------------------------------------------------

@test "ec_parse_args defaults to all tools and tilth+context7" {
    ec_parse_args
    [[ "$EC_TOOLS" == *"gh"* && "$EC_TOOLS" == *"tilth"* ]]
    [[ "$EC_MCP" == "tilth,context7" ]]
    [[ "$EC_HARNESS" == "auto" ]]
    [[ "$EC_WITH_EDIT" == "1" ]]
    [[ "$EC_DRY_RUN" == "0" ]]
    [[ "$EC_DO_HELP" == "0" ]]
}

@test "ec_parse_args --tools with value parses comma list" {
    ec_parse_args --tools ripgrep,jq
    [[ "$EC_TOOLS" == "ripgrep,jq" ]]
}

@test "ec_parse_args --tools=value parses inline value" {
    ec_parse_args --tools=fd
    [[ "$EC_TOOLS" == "fd" ]]
}

@test "ec_parse_args --skip-mcp sets MCP to none" {
    ec_parse_args --skip-mcp
    [[ "$EC_MCP" == "none" ]]
}

@test "ec_parse_args --no-edit clears WITH_EDIT" {
    ec_parse_args --no-edit
    [[ "$EC_WITH_EDIT" == "0" ]]
}

@test "ec_parse_args --dry-run sets DRY_RUN" {
    ec_parse_args --dry-run
    [[ "$EC_DRY_RUN" == "1" ]]
}

@test "ec_parse_args --harness overrides default harness" {
    ec_parse_args --harness cursor
    [[ "$EC_HARNESS" == "cursor" ]]
}

@test "ec_parse_args --harness accepts comma-separated harness list" {
    ec_parse_args --harness cursor,codex
    [[ "$EC_HARNESS" == "cursor,codex" ]]
}

@test "ec_parse_args -h sets DO_HELP" {
    ec_parse_args -h
    [[ "$EC_DO_HELP" == "1" ]]
}

@test "ec_parse_args --help sets DO_HELP" {
    ec_parse_args --help
    [[ "$EC_DO_HELP" == "1" ]]
}

@test "ec_parse_args rejects unknown flag with exit code 2" {
    run ec_parse_args --bogus
    [ "$status" -eq 2 ]
    [[ "$output" == *"Unknown option"* ]]
}

@test "ec_parse_args rejects positional arg with exit code 2" {
    run ec_parse_args some-arg
    [ "$status" -eq 2 ]
    [[ "$output" == *"Unexpected positional"* ]]
}

@test "ec_parse_args --tools without value fails" {
    run ec_parse_args --tools
    [ "$status" -eq 2 ]
}

@test "ec_parse_args --mcp without value fails" {
    run ec_parse_args --mcp
    [ "$status" -eq 2 ]
}

@test "ec_parse_args rejects unknown tool selection" {
    run ec_parse_args --tools ripgrep,foobar
    [ "$status" -eq 2 ]
    [[ "$output" == *"foobar"* ]]
}

@test "ec_parse_args rejects unknown mcp selection" {
    run ec_parse_args --mcp tilth,bogus
    [ "$status" -eq 2 ]
    [[ "$output" == *"bogus"* ]]
}

@test "ec_parse_args -- terminates option parsing" {
    ec_parse_args --dry-run --
    [[ "$EC_DRY_RUN" == "1" ]]
}

# -- ec_detect_os -------------------------------------------------------------

@test "ec_detect_os returns 0 when uname reports Darwin" {
    cat > "$STUB_BIN/uname" <<'STUB'
#!/usr/bin/env bash
echo Darwin
STUB
    chmod +x "$STUB_BIN/uname"
    run ec_detect_os
    [ "$status" -eq 0 ]
}

@test "ec_detect_os returns 1 when uname reports Linux" {
    cat > "$STUB_BIN/uname" <<'STUB'
#!/usr/bin/env bash
echo Linux
STUB
    chmod +x "$STUB_BIN/uname"
    run ec_detect_os
    [ "$status" -eq 1 ]
}

# -- ec_ensure_homebrew -------------------------------------------------------

@test "ec_ensure_homebrew passes when brew exists" {
    make_stub brew
    run ec_ensure_homebrew
    [ "$status" -eq 0 ]
}

@test "ec_ensure_homebrew fails with hint when brew missing" {
    run ec_ensure_homebrew
    [ "$status" -eq 1 ]
    [[ "$output" == *"Homebrew is required"* ]]
    [[ "$output" == *"https://brew.sh"* ]]
}

# -- ec_brew_install_if_missing ----------------------------------------------

@test "ec_brew_install_if_missing skips when binary already on PATH" {
    make_stub jq
    make_stub brew
    export EC_BREW="$STUB_BIN/brew"
    run ec_brew_install_if_missing jq
    [ "$status" -eq 0 ]
    [[ "$output" == *"already installed"* ]]
    # brew should NOT have been invoked
    [ ! -s "$STUB_LOG" ] || ! grep -q "^brew install" "$STUB_LOG"
}

@test "ec_brew_install_if_missing dry-run prints would-run line" {
    EC_DRY_RUN=1 run ec_brew_install_if_missing ripgrep
    [ "$status" -eq 0 ]
    [[ "$output" == *"would run 'brew install ripgrep'"* ]]
}

@test "ec_brew_install_if_missing invokes brew when missing" {
    make_stub brew
    export EC_BREW="$STUB_BIN/brew"
    run ec_brew_install_if_missing ripgrep
    [ "$status" -eq 0 ]
    grep -q "^brew install ripgrep$" "$STUB_LOG"
}

@test "ec_brew_install_if_missing surfaces brew failure" {
    make_stub brew 1
    export EC_BREW="$STUB_BIN/brew"
    run ec_brew_install_if_missing ripgrep
    [ "$status" -ne 0 ]
}

# -- ec_install_tools ---------------------------------------------------------

@test "ec_install_tools (dry-run) iterates each formula in the list" {
    PATH="$STUB_BIN" EC_DRY_RUN=1 run ec_install_tools "ripgrep,jq,fd"
    [ "$status" -eq 0 ]
    [[ "$output" == *"would run 'brew install ripgrep'"* ]]
    [[ "$output" == *"would run 'brew install jq'"* ]]
    [[ "$output" == *"would run 'brew install fd'"* ]]
}

@test "ec_install_tools routes tilth through ec_install_tilth, not brew" {
    make_stub cargo
    EC_CARGO="$STUB_BIN/cargo" EC_DRY_RUN=1 run ec_install_tools "tilth"
    [ "$status" -eq 0 ]
    [[ "$output" == *"cargo install tilth"* ]]
    [[ "$output" != *"brew install tilth"* ]]
}

# -- ec_install_tilth ---------------------------------------------------------

@test "ec_install_tilth short-circuits when tilth already on PATH" {
    make_stub tilth
    run ec_install_tilth
    [ "$status" -eq 0 ]
    [[ "$output" == *"already installed"* ]]
}

@test "ec_install_tilth dry-run prefers cargo when both cargo and npm exist" {
    make_stub cargo
    make_stub npm
    EC_CARGO="$STUB_BIN/cargo" EC_NPM="$STUB_BIN/npm" EC_DRY_RUN=1 \
        run ec_install_tilth
    [ "$status" -eq 0 ]
    [[ "$output" == *"would run"* ]]
    [[ "$output" == *"cargo install tilth"* ]]
    [[ "$output" != *"npm install -g tilth"* ]]
}

@test "ec_install_tilth invokes cargo when not dry-run" {
    make_stub cargo
    export EC_CARGO="$STUB_BIN/cargo"
    run ec_install_tilth
    [ "$status" -eq 0 ]
    grep -q "^cargo install tilth$" "$STUB_LOG"
}

@test "ec_install_tilth falls back to npm install -g when cargo missing" {
    make_stub npm
    EC_NPM="$STUB_BIN/npm" EC_DRY_RUN=1 run ec_install_tilth
    [ "$status" -eq 0 ]
    [[ "$output" == *"npm install -g tilth"* ]]
    [[ "$output" == *"cargo not found"* ]]
}

@test "ec_install_tilth invokes npm install -g when cargo missing" {
    make_stub npm
    export EC_NPM="$STUB_BIN/npm"
    run ec_install_tilth
    [ "$status" -eq 0 ]
    grep -q "^npm install -g tilth$" "$STUB_LOG"
}

@test "ec_install_tilth fails clearly when neither cargo nor npm present" {
    run ec_install_tilth
    [ "$status" -eq 1 ]
    [[ "$output" == *"needs cargo (Rust) or npm"* ]]
    [[ "$output" == *"rustup.rs"* ]]
}

# -- ec_install_mcp_tilth -----------------------------------------------------

@test "ec_install_mcp_tilth fails clearly when tilth CLI missing" {
    run ec_install_mcp_tilth claude-code 1
    [ "$status" -ne 0 ]
    [[ "$output" == *"tilth CLI is not installed"* ]]
}

@test "ec_install_mcp_tilth dry-run shows install command with --edit" {
    make_stub tilth
    EC_TILTH="$STUB_BIN/tilth" EC_DRY_RUN=1 run ec_install_mcp_tilth claude-code 1
    [ "$status" -eq 0 ]
    [[ "$output" == *"install claude-code --edit"* ]]
}

@test "ec_install_mcp_tilth dry-run omits --edit when WITH_EDIT=0" {
    make_stub tilth
    EC_TILTH="$STUB_BIN/tilth" EC_DRY_RUN=1 run ec_install_mcp_tilth claude-code 0
    [ "$status" -eq 0 ]
    [[ "$output" != *"--edit"* ]]
}

@test "ec_install_mcp_tilth invokes tilth install when not dry-run" {
    make_stub tilth
    export EC_TILTH="$STUB_BIN/tilth"
    run ec_install_mcp_tilth claude-code 1
    [ "$status" -eq 0 ]
    grep -q "^tilth install claude-code --edit$" "$STUB_LOG"
}

# -- ec_install_mcp_context7 / tavily / crg ----------------------------------

@test "ec_install_mcp_context7 warns and skips for non-claude harness" {
    run ec_install_mcp_context7 cursor
    [ "$status" -eq 0 ]
    [[ "$output" == *"only claude-code is auto-registered"* ]]
}

@test "ec_install_mcp_context7 fails when claude CLI missing" {
    run ec_install_mcp_context7 claude-code
    [ "$status" -ne 0 ]
    [[ "$output" == *"claude CLI not found"* ]]
}

@test "ec_install_mcp_context7 dry-run prints would-run with package name" {
    make_stub claude
    EC_CLAUDE="$STUB_BIN/claude" EC_DRY_RUN=1 run ec_install_mcp_context7 claude-code
    [ "$status" -eq 0 ]
    [[ "$output" == *"@upstash/context7-mcp@latest"* ]]
}

@test "ec_install_mcp_context7 dry-run shows resolved \$claude / \$npx paths" {
    make_stub claude
    make_stub npx
    EC_CLAUDE="$STUB_BIN/claude" EC_NPX="$STUB_BIN/npx" EC_DRY_RUN=1 \
        run ec_install_mcp_context7 claude-code
    [ "$status" -eq 0 ]
    # Resolved overrides land in the dry-run preview, not literal "claude"/"npx".
    [[ "$output" == *"$STUB_BIN/claude mcp add context7 -- $STUB_BIN/npx -y @upstash/context7-mcp@latest"* ]]
}

@test "ec_install_mcp_context7 honors EC_NPX in real invocation" {
    make_stub claude
    cat > "$STUB_BIN/my-npx" <<'STUB'
#!/usr/bin/env bash
echo "my-npx $*" >> "$STUB_LOG"
exit 0
STUB
    chmod +x "$STUB_BIN/my-npx"
    EC_CLAUDE="$STUB_BIN/claude" EC_NPX="$STUB_BIN/my-npx" \
        run ec_install_mcp_context7 claude-code
    [ "$status" -eq 0 ]
    # The claude stub captures argv; assert the EC_NPX override was forwarded.
    grep -q "^claude mcp add context7 -- $STUB_BIN/my-npx -y @upstash/context7-mcp@latest$" "$STUB_LOG"
}

@test "ec_install_mcp_tavily warns when TAVILY_API_KEY unset (dry-run)" {
    make_stub claude
    unset TAVILY_API_KEY
    EC_CLAUDE="$STUB_BIN/claude" EC_DRY_RUN=1 run ec_install_mcp_tavily claude-code
    [ "$status" -eq 0 ]
    [[ "$output" == *"TAVILY_API_KEY is not set"* ]]
}

@test "ec_install_mcp_tavily dry-run shows resolved \$claude / \$npx paths" {
    make_stub claude
    make_stub npx
    EC_CLAUDE="$STUB_BIN/claude" EC_NPX="$STUB_BIN/npx" EC_DRY_RUN=1 \
        run ec_install_mcp_tavily claude-code
    [ "$status" -eq 0 ]
    [[ "$output" == *"$STUB_BIN/claude mcp add tavily -- $STUB_BIN/npx -y tavily-mcp"* ]]
}

# -- ec_install_crg_cli -------------------------------------------------------

@test "ec_install_crg_cli prefers uv over pipx and pip" {
    make_stub uv
    make_stub pipx
    make_stub pip
    EC_UV="$STUB_BIN/uv" EC_PIPX="$STUB_BIN/pipx" EC_PIP="$STUB_BIN/pip" \
        EC_DRY_RUN=1 run ec_install_crg_cli
    [ "$status" -eq 0 ]
    [[ "$output" == *"uv tool install code-review-graph[embeddings]"* ]]
    [[ "$output" != *"pipx install"* ]]
    [[ "$output" != *"pip install"* ]]
}

@test "ec_install_crg_cli falls back to pipx when uv missing" {
    make_stub pipx
    make_stub pip
    EC_PIPX="$STUB_BIN/pipx" EC_PIP="$STUB_BIN/pip" \
        EC_DRY_RUN=1 run ec_install_crg_cli
    [ "$status" -eq 0 ]
    [[ "$output" == *"pipx install code-review-graph[embeddings]"* ]]
    [[ "$output" != *"uv tool"* ]]
}

@test "ec_install_crg_cli falls back to 'pip install --user' last with a warning" {
    make_stub pip
    EC_PIP="$STUB_BIN/pip" EC_DRY_RUN=1 run ec_install_crg_cli
    [ "$status" -eq 0 ]
    [[ "$output" == *"falling back to 'pip install --user'"* ]]
    [[ "$output" == *"pip install --user code-review-graph[embeddings]"* ]]
}

@test "ec_install_crg_cli fails clearly when uv, pipx, and pip are all missing" {
    PATH="$STUB_BIN" run ec_install_crg_cli
    [ "$status" -eq 1 ]
    [[ "$output" == *"needs uv, pipx, or pip"* ]]
}

@test "ec_install_crg_cli invokes uv tool install with embeddings extra when not dry-run" {
    make_stub uv
    export EC_UV="$STUB_BIN/uv"
    run ec_install_crg_cli
    [ "$status" -eq 0 ]
    grep -q "^uv tool install code-review-graph\[embeddings\]$" "$STUB_LOG"
}

@test "ec_install_crg_cli honors EC_CRG_SPEC override (bare CLI, no extras)" {
    make_stub uv
    EC_UV="$STUB_BIN/uv" EC_CRG_SPEC="code-review-graph" EC_DRY_RUN=1 \
        run ec_install_crg_cli
    [ "$status" -eq 0 ]
    [[ "$output" == *"uv tool install code-review-graph"* ]]
    [[ "$output" != *"code-review-graph[embeddings]"* ]]
}

# -- ec_install_mcp_crg -------------------------------------------------------

@test "ec_install_mcp_crg installs CLI then registers when binary missing" {
    make_stub uv
    EC_UV="$STUB_BIN/uv" EC_CRG="$STUB_BIN/code-review-graph-not-real" \
        EC_DRY_RUN=1 run ec_install_mcp_crg claude-code
    [ "$status" -eq 0 ]
    [[ "$output" == *"uv tool install code-review-graph[embeddings]"* ]]
    [[ "$output" == *"install --platform claude-code"* ]]
}

@test "ec_install_mcp_crg invokes crg install for present binary" {
    make_stub code-review-graph
    export EC_CRG="$STUB_BIN/code-review-graph"
    run ec_install_mcp_crg claude-code
    [ "$status" -eq 0 ]
    grep -q "^code-review-graph install --platform claude-code$" "$STUB_LOG"
}

@test "ec_install_mcp_crg fails with PATH hint when binary still missing after install" {
    # Simulate the common 'pip install --user' case: pip succeeds but the
    # binary lands in a directory that's not on PATH, so the post-install
    # ec_cmd_exists check still fails.
    make_stub pip
    export EC_PIP="$STUB_BIN/pip"
    # EC_CRG points at a path that will never exist on PATH.
    export EC_CRG="$BATS_TEST_TMPDIR/nope/code-review-graph"
    run ec_install_mcp_crg claude-code
    [ "$status" -eq 1 ]
    [[ "$output" == *"install succeeded but"* ]]
    [[ "$output" == *"not on PATH"* ]]
    [[ "$output" == *"pipx ensurepath"* ]]
    # Crucially, the registration step must NOT fire when the binary is
    # still missing — otherwise the user gets the generic shell error we're
    # trying to replace with a targeted hint.
    ! grep -q " install --platform " "$STUB_LOG" || false
}

# -- ec_install_skills --------------------------------------------------------

@test "ec_detect_harnesses finds installed main-line harness CLIs" {
    make_stub claude
    make_stub cursor
    make_stub codex
    EC_CLAUDE="$STUB_BIN/claude" EC_CURSOR="$STUB_BIN/cursor" EC_CODEX="$STUB_BIN/codex" \
        run ec_detect_harnesses
    [ "$status" -eq 0 ]
    [[ "$output" == *"claude-code"* ]]
    [[ "$output" == *"cursor"* ]]
    [[ "$output" == *"codex"* ]]
}

@test "ec_resolve_harnesses auto returns every detected harness" {
    make_stub claude
    make_stub cursor
    EC_CLAUDE="$STUB_BIN/claude" EC_CURSOR="$STUB_BIN/cursor" EC_CODEX="$STUB_BIN/missing-codex" \
        run ec_resolve_harnesses auto
    [ "$status" -eq 0 ]
    [[ "$output" == *"claude-code"* ]]
    [[ "$output" == *"cursor"* ]]
    [[ "$output" != *"codex"* ]]
}

@test "ec_resolve_harnesses auto falls back to claude-code when nothing detected" {
    EC_CLAUDE="$STUB_BIN/missing-claude" EC_CURSOR="$STUB_BIN/missing-cursor" EC_CODEX="$STUB_BIN/missing-codex" \
        run ec_resolve_harnesses auto
    [ "$status" -eq 0 ]
    [[ "$output" == *"falling back to claude-code"* ]]
    [[ "$output" == *"claude-code"* ]]
}

@test "ec_resolve_harnesses keeps explicit comma-separated harnesses" {
    run ec_resolve_harnesses cursor,codex
    [ "$status" -eq 0 ]
    [[ "$output" == *"cursor"* ]]
    [[ "$output" == *"codex"* ]]
}

@test "ec_install_skills warns and returns 0 when gh CLI missing" {
    PATH="$STUB_BIN" run ec_install_skills claude-code
    [ "$status" -eq 0 ]
    [[ "$output" == *"gh CLI not found"* ]]
}

@test "ec_install_skills dry-run lists every shipped skill with --force" {
    make_stub gh
    PATH="$STUB_BIN" EC_GH=gh EC_DRY_RUN=1 run ec_install_skills claude-code
    [ "$status" -eq 0 ]
    # Spot-check first, last, and a representative middle skill in the list.
    [[ "$output" == *"would run 'gh skill install paulnsorensen/easy-cheese age --agent claude-code --scope user --force'"* ]]
    [[ "$output" == *"would run 'gh skill install paulnsorensen/easy-cheese cook --agent claude-code --scope user --force'"* ]]
    [[ "$output" == *"would run 'gh skill install paulnsorensen/easy-cheese press --agent claude-code --scope user --force'"* ]]
    # Confirm we never emit the broken --all flag again.
    [[ "$output" != *"--all"* ]]
}

@test "ec_install_skills dry-run honors picked harness" {
    make_stub gh
    EC_GH="$STUB_BIN/gh" EC_DRY_RUN=1 run ec_install_skills cursor
    [ "$status" -eq 0 ]
    [[ "$output" == *"--agent cursor"* ]]
    [[ "$output" != *"--agent claude-code"* ]]
}

@test "ec_install_skills_for_harnesses installs every skill into every harness" {
    make_stub gh
    EC_GH="$STUB_BIN/gh" EC_DRY_RUN=1 run ec_install_skills_for_harnesses $'cursor\ncodex'
    [ "$status" -eq 0 ]
    [[ "$output" == *"--agent cursor"* ]]
    [[ "$output" == *"--agent codex"* ]]
    [[ "$output" != *"--agent claude-code"* ]]
}

@test "ec_install_skills warns and returns 1 when gh is unauthenticated" {
    cat > "$STUB_BIN/gh" <<'STUB'
#!/usr/bin/env bash
echo "gh $*" >> "$STUB_LOG"
# Simulate `gh auth status` failure when called as 'gh auth status'.
if [[ "$1" == "auth" && "$2" == "status" ]]; then
    exit 1
fi
exit 0
STUB
    chmod +x "$STUB_BIN/gh"
    export EC_GH="$STUB_BIN/gh"
    run ec_install_skills claude-code
    [ "$status" -eq 1 ]
    [[ "$output" == *"gh is not authenticated"* ]]
    [[ "$output" == *"gh auth login"* ]]
}

@test "ec_discover_skills returns names from gh api stdout" {
    cat > "$STUB_BIN/gh" <<'STUB'
#!/usr/bin/env bash
echo "gh $*" >> "$STUB_LOG"
if [[ "$1" == "api" ]]; then
    printf 'alpha\nbeta\ngamma\n'
    exit 0
fi
exit 0
STUB
    chmod +x "$STUB_BIN/gh"
    run ec_discover_skills "$STUB_BIN/gh"
    [ "$status" -eq 0 ]
    [[ "$output" == *"alpha"* && "$output" == *"beta"* && "$output" == *"gamma"* ]]
    grep -q "^gh api repos/paulnsorensen/easy-cheese/contents/skills " "$STUB_LOG"
}

@test "ec_discover_skills returns empty when gh api fails" {
    cat > "$STUB_BIN/gh" <<'STUB'
#!/usr/bin/env bash
echo "gh $*" >> "$STUB_LOG"
exit 1
STUB
    chmod +x "$STUB_BIN/gh"
    run ec_discover_skills "$STUB_BIN/gh"
    [ "$status" -ne 0 ]
    [[ -z "$output" ]]
}

@test "ec_install_skills uses live list when gh api discovery succeeds" {
    cat > "$STUB_BIN/gh" <<'STUB'
#!/usr/bin/env bash
echo "gh $*" >> "$STUB_LOG"
if [[ "$1" == "api" ]]; then
    printf 'alpha\nbeta\ngamma\n'
    exit 0
fi
exit 0
STUB
    chmod +x "$STUB_BIN/gh"
    export EC_GH="$STUB_BIN/gh"
    run ec_install_skills claude-code
    [ "$status" -eq 0 ]
    grep -q "^gh auth status$" "$STUB_LOG"
    grep -q "^gh api repos/paulnsorensen/easy-cheese/contents/skills " "$STUB_LOG"
    grep -q "^gh skill install paulnsorensen/easy-cheese alpha --agent claude-code --scope user --force$" "$STUB_LOG"
    grep -q "^gh skill install paulnsorensen/easy-cheese beta --agent claude-code --scope user --force$" "$STUB_LOG"
    grep -q "^gh skill install paulnsorensen/easy-cheese gamma --agent claude-code --scope user --force$" "$STUB_LOG"
    # Exactly the three discovered skills — fallback list was NOT used.
    [ "$(grep -c '^gh skill install ' "$STUB_LOG")" -eq 3 ]
    [[ "$output" != *"using embedded fallback list"* ]]
    ! grep -q -- "--all" "$STUB_LOG" || false
}

@test "ec_install_skills falls back to embedded list when gh api fails" {
    cat > "$STUB_BIN/gh" <<'STUB'
#!/usr/bin/env bash
echo "gh $*" >> "$STUB_LOG"
if [[ "$1" == "api" ]]; then
    exit 1
fi
exit 0
STUB
    chmod +x "$STUB_BIN/gh"
    export EC_GH=gh
    run ec_install_skills claude-code
    [ "$status" -eq 0 ]
    [[ "$output" == *"using embedded fallback list"* ]]
    # Fallback list ships one install per embedded skill; assert via
    # spot-checks plus an exact count so accidental drift surfaces in CI.
    grep -q "^gh skill install paulnsorensen/easy-cheese age --agent claude-code --scope user --force$" "$STUB_LOG"
    grep -q "^gh skill install paulnsorensen/easy-cheese press --agent claude-code --scope user --force$" "$STUB_LOG"
    grep -q "^gh skill install paulnsorensen/easy-cheese ultracook --agent claude-code --scope user --force$" "$STUB_LOG"
    grep -q "^gh skill install paulnsorensen/easy-cheese cheese-factory --agent claude-code --scope user --force$" "$STUB_LOG"
    [ "$(grep -c '^gh skill install ' "$STUB_LOG")" -eq "$(count_skills)" ]
}

@test "ec_install_skills falls back to embedded list when gh api returns empty" {
    # Basic stub: every gh call exits 0 with no stdout, including `gh api`.
    make_stub gh
    export EC_GH=gh
    run ec_install_skills claude-code
    [ "$status" -eq 0 ]
    [[ "$output" == *"using embedded fallback list"* ]]
    [ "$(grep -c '^gh skill install ' "$STUB_LOG")" -eq "$(count_skills)" ]
}

@test "ec_install_skills passes --pin when EC_SKILL_REF is set" {
    cat > "$STUB_BIN/gh" <<'STUB'
#!/usr/bin/env bash
echo "gh $*" >> "$STUB_LOG"
case "$1" in
    api) printf 'alpha\nbeta\n'; exit 0 ;;
esac
exit 0
STUB
    chmod +x "$STUB_BIN/gh"
    EC_GH="$STUB_BIN/gh" EC_SKILL_REF="abc123def" run ec_install_skills claude-code
    [ "$status" -eq 0 ]
    # --pin should be threaded into every install call, slotted before --agent.
    grep -q "^gh skill install paulnsorensen/easy-cheese alpha --pin abc123def --agent claude-code --scope user --force$" "$STUB_LOG"
    grep -q "^gh skill install paulnsorensen/easy-cheese beta --pin abc123def --agent claude-code --scope user --force$" "$STUB_LOG"
}

@test "ec_install_skills dry-run echoes --pin in the would-run line when EC_SKILL_REF is set" {
    make_stub gh
    EC_GH="$STUB_BIN/gh" EC_SKILL_REF="v1.2.3" EC_DRY_RUN=1 run ec_install_skills claude-code
    [ "$status" -eq 0 ]
    [[ "$output" == *"--pin v1.2.3"* ]]
}

@test "ec_install_skills returns non-zero when any skill install fails" {
    cat > "$STUB_BIN/gh" <<'STUB'
#!/usr/bin/env bash
echo "gh $*" >> "$STUB_LOG"
case "$1" in
    api) printf 'alpha\nbeta\ngamma\n'; exit 0 ;;
esac
# Auth ok, but fail when installing the 'beta' skill.
if [[ "$1" == "skill" && "$2" == "install" && "$4" == "beta" ]]; then
    exit 1
fi
exit 0
STUB
    chmod +x "$STUB_BIN/gh"
    export EC_GH="$STUB_BIN/gh"
    run ec_install_skills claude-code
    [ "$status" -eq 1 ]
    [[ "$output" == *"failed to install beta"* ]]
    # Loop kept going past the failure — every other skill was still attempted.
    [ "$(grep -c '^gh skill install ' "$STUB_LOG")" -eq 3 ]
}

# -- ec_install_mcp -----------------------------------------------------------

@test "ec_install_mcp dispatches 'none' as a no-op log line" {
    run ec_install_mcp none claude-code 1
    [ "$status" -eq 0 ]
    [[ "$output" == *"skipping"* ]]
}

@test "ec_install_mcp rejects unknown server" {
    run ec_install_mcp wensleydale claude-code 1
    [ "$status" -ne 0 ]
    [[ "$output" == *"Unknown MCP server"* ]]
}

# -- ec_main full-flow --------------------------------------------------------

@test "ec_main --help prints usage and exits 0" {
    run ec_main --help
    [ "$status" -eq 0 ]
    [[ "$output" == *"easy-cheese installer"* ]]
    [[ "$output" == *"--tools"* ]]
    [[ "$output" == *"--dry-run"* ]]
}

@test "ec_main rejects non-Darwin OS" {
    cat > "$STUB_BIN/uname" <<'STUB'
#!/usr/bin/env bash
echo Linux
STUB
    chmod +x "$STUB_BIN/uname"
    run ec_main --dry-run
    [ "$status" -ne 0 ]
    [[ "$output" == *"macOS only"* ]]
}

@test "ec_main fails when Homebrew missing on macOS" {
    cat > "$STUB_BIN/uname" <<'STUB'
#!/usr/bin/env bash
echo Darwin
STUB
    chmod +x "$STUB_BIN/uname"
    # Note: no brew stub in PATH, EC_BREW unset.
    unset EC_BREW
    run ec_main --skip-mcp
    [ "$status" -ne 0 ]
    [[ "$output" == *"Homebrew is required"* ]]
}

@test "ec_main full --dry-run on macOS prints all tool, skill, and MCP actions" {
    cat > "$STUB_BIN/uname" <<'STUB'
#!/usr/bin/env bash
echo Darwin
STUB
    chmod +x "$STUB_BIN/uname"
    make_stub brew
    make_stub cargo
    make_stub gh
    make_stub claude
    make_stub tilth
    ln -sf /bin/bash "$STUB_BIN/bash"
    PATH="$STUB_BIN" \
    EC_BREW=brew \
    EC_CARGO=cargo \
    EC_GH=gh \
    EC_CLAUDE=claude \
    EC_TILTH=tilth \
        run ec_main --dry-run
    [ "$status" -eq 0 ]
    [[ "$output" == *"gh: already installed (gh on PATH)"* ]]
    [[ "$output" == *"would run 'brew install ripgrep'"* ]]
    # tilth is detected on PATH and should never route through brew.
    [[ "$output" == *"tilth: already installed (tilth on PATH)"* ]]
    [[ "$output" != *"brew install tilth"* ]]
    [[ "$output" != *"paulnsorensen/tap/tilth"* ]]
    # Skills install runs as part of the harness pick stage — one entry per
    # shipped skill, never the broken --all flag.
    [[ "$output" == *"gh skill install paulnsorensen/easy-cheese age --agent claude-code --scope user --force"* ]]
    [[ "$output" == *"gh skill install paulnsorensen/easy-cheese press --agent claude-code --scope user --force"* ]]
    [[ "$output" != *"--all"* ]]
    [[ "$output" == *"install claude-code --edit"* ]]
    [[ "$output" == *"@upstash/context7-mcp@latest"* ]]
    [[ "$output" == *"Done."* ]]
}

@test "ec_main auto-installs skills into each detected main-line harness" {
    cat > "$STUB_BIN/uname" <<'STUB'
#!/usr/bin/env bash
echo Darwin
STUB
    chmod +x "$STUB_BIN/uname"
    make_stub brew
    make_stub gh
    make_stub claude
    make_stub cursor
    make_stub codex
    EC_BREW="$STUB_BIN/brew" \
    EC_GH="$STUB_BIN/gh" \
    EC_CLAUDE="$STUB_BIN/claude" \
    EC_CURSOR="$STUB_BIN/cursor" \
    EC_CODEX="$STUB_BIN/codex" \
        run ec_main --skip-tools --skip-mcp
    [ "$status" -eq 0 ]
    grep -q "^gh skill install paulnsorensen/easy-cheese age --agent claude-code --scope user --force$" "$STUB_LOG"
    grep -q "^gh skill install paulnsorensen/easy-cheese age --agent cursor --scope user --force$" "$STUB_LOG"
    grep -q "^gh skill install paulnsorensen/easy-cheese age --agent codex --scope user --force$" "$STUB_LOG"
    local expected_harness_count=3 skill_count
    skill_count=$(count_skills)
    [ "$(grep -c '^gh skill install ' "$STUB_LOG")" -eq $((skill_count * expected_harness_count)) ]
}

@test "ec_main --skip-tools --mcp tilth registers only tilth (still runs skills)" {
    cat > "$STUB_BIN/uname" <<'STUB'
#!/usr/bin/env bash
echo Darwin
STUB
    chmod +x "$STUB_BIN/uname"
    make_stub tilth
    make_stub gh
    EC_TILTH="$STUB_BIN/tilth" EC_GH="$STUB_BIN/gh" \
        run ec_main --skip-tools --mcp tilth
    [ "$status" -eq 0 ]
    grep -q "^tilth install claude-code --edit$" "$STUB_LOG"
    grep -q "^gh skill install paulnsorensen/easy-cheese age --agent claude-code --scope user --force$" "$STUB_LOG"
    grep -q "^gh skill install paulnsorensen/easy-cheese press --agent claude-code --scope user --force$" "$STUB_LOG"
    # One install per fallback skill, no broken --all flag.
    [ "$(grep -c '^gh skill install ' "$STUB_LOG")" -eq "$(count_skills)" ]
    # No brew calls should have happened.
    ! grep -q "^brew" "$STUB_LOG" || false
}
