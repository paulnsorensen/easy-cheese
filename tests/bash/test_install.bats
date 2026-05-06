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

# -- ec_tool_binary / ec_tool_formula -----------------------------------------

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

@test "ec_tool_formula taps tilth from paulnsorensen/tap" {
    [[ "$(ec_tool_formula tilth)" == "paulnsorensen/tap/tilth" ]]
    [[ "$(ec_tool_formula ripgrep)" == "ripgrep" ]]
    [[ "$(ec_tool_formula gh)" == "gh" ]]
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
    [[ "$EC_HARNESS" == "claude-code" ]]
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

@test "ec_brew_install_if_missing dry-run uses tap formula for tilth" {
    EC_DRY_RUN=1 run ec_brew_install_if_missing tilth
    [ "$status" -eq 0 ]
    [[ "$output" == *"paulnsorensen/tap/tilth"* ]]
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
    EC_DRY_RUN=1 run ec_install_tools "ripgrep,jq,fd"
    [ "$status" -eq 0 ]
    [[ "$output" == *"would run 'brew install ripgrep'"* ]]
    [[ "$output" == *"would run 'brew install jq'"* ]]
    [[ "$output" == *"would run 'brew install fd'"* ]]
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

@test "ec_install_mcp_tavily warns when TAVILY_API_KEY unset (dry-run)" {
    make_stub claude
    unset TAVILY_API_KEY
    EC_CLAUDE="$STUB_BIN/claude" EC_DRY_RUN=1 run ec_install_mcp_tavily claude-code
    [ "$status" -eq 0 ]
    [[ "$output" == *"TAVILY_API_KEY is not set"* ]]
}

@test "ec_install_mcp_crg dry-run installs via pip when missing" {
    make_stub pip
    EC_PIP="$STUB_BIN/pip" EC_CRG="$STUB_BIN/code-review-graph-not-real" \
        EC_DRY_RUN=1 run ec_install_mcp_crg claude-code
    [ "$status" -eq 0 ]
    [[ "$output" == *"would run"* ]]
    [[ "$output" == *"install code-review-graph"* ]]
}

@test "ec_install_mcp_crg invokes crg install for present binary" {
    make_stub code-review-graph
    export EC_CRG="$STUB_BIN/code-review-graph"
    run ec_install_mcp_crg claude-code
    [ "$status" -eq 0 ]
    grep -q "^code-review-graph install --platform claude-code$" "$STUB_LOG"
}

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

@test "ec_main full --dry-run on macOS prints all tool actions" {
    cat > "$STUB_BIN/uname" <<'STUB'
#!/usr/bin/env bash
echo Darwin
STUB
    chmod +x "$STUB_BIN/uname"
    make_stub brew
    make_stub tilth
    make_stub claude
    EC_BREW="$STUB_BIN/brew" \
    EC_TILTH="$STUB_BIN/tilth" \
    EC_CLAUDE="$STUB_BIN/claude" \
        run ec_main --dry-run
    [ "$status" -eq 0 ]
    [[ "$output" == *"would run 'brew install gh'"* ]]
    [[ "$output" == *"would run 'brew install ripgrep'"* ]]
    [[ "$output" == *"paulnsorensen/tap/tilth"* ]]
    [[ "$output" == *"install claude-code --edit"* ]]
    [[ "$output" == *"@upstash/context7-mcp@latest"* ]]
    [[ "$output" == *"Done."* ]]
}

@test "ec_main --skip-tools --mcp tilth registers only tilth" {
    cat > "$STUB_BIN/uname" <<'STUB'
#!/usr/bin/env bash
echo Darwin
STUB
    chmod +x "$STUB_BIN/uname"
    make_stub tilth
    EC_TILTH="$STUB_BIN/tilth" \
        run ec_main --skip-tools --mcp tilth
    [ "$status" -eq 0 ]
    grep -q "^tilth install claude-code --edit$" "$STUB_LOG"
    # No brew calls should have happened.
    ! grep -q "^brew" "$STUB_LOG" || false
}
