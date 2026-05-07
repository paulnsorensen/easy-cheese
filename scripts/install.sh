#!/usr/bin/env bash
#
# easy-cheese installer — sets up the CLI tools and MCP servers used by the
# easy-cheese skills on macOS.
#
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/paulnsorensen/easy-cheese/main/scripts/install.sh | bash
#
# Or with options:
#   curl -fsSL https://raw.githubusercontent.com/paulnsorensen/easy-cheese/main/scripts/install.sh | bash -s -- --skip-mcp
#
# Run `bash install.sh --help` for the full flag list.

# strict-mode is enabled inside the BASH_SOURCE guard at the bottom of the
# file so sourcing (e.g. from the bats suite) does not mutate the caller's
# shell options.

# All known CLI tools. tilth is included but installed via cargo/npm (not
# brew — upstream jahala/tilth does not ship a Homebrew formula).
EC_KNOWN_TOOLS="gh ripgrep fd jq ast-grep git-delta just mergiraf tilth"

# Repository the installer pulls skills from. Centralized so discovery and
# install both reference the same source.
EC_SKILL_REPO="paulnsorensen/easy-cheese"

# Embedded fallback list of skill names. The installer normally discovers
# the live set via 'gh api repos/.../contents/skills' so it self-heals when
# new skills land — this list is only used when the API call is
# unavailable (offline, rate-limited, repo temporarily private). Kept
# loosely in sync with skills/ but not load-bearing for happy-path runs.
EC_FALLBACK_SKILLS="age briesearch cheese cheez-read cheez-search cheez-write cook culture cure melt mold press"

# Default selections.
EC_DEFAULT_TOOLS="$EC_KNOWN_TOOLS"
EC_DEFAULT_MCP="tilth context7"

# Map a brew formula name to the binary it installs (when they differ).
ec_tool_binary() {
    case "$1" in
        ripgrep)   echo "rg" ;;
        ast-grep)  echo "sg" ;;
        git-delta) echo "delta" ;;
        *)         echo "$1" ;;
    esac
}

ec_log() {
    printf '\033[1;36m==>\033[0m %s\n' "$*"
}

ec_warn() {
    printf '\033[1;33m!! \033[0m %s\n' "$*" >&2
}

ec_err() {
    printf '\033[1;31mxx \033[0m %s\n' "$*" >&2
}

ec_usage() {
    cat <<'USAGE'
easy-cheese installer (macOS)

Usage:
  install.sh [options]

Options:
  --tools <list>       Comma-separated CLI tools to install. Default: all.
                       Choices: gh, ripgrep, fd, jq, ast-grep, git-delta,
                                just, mergiraf, tilth
  --mcp <list>         Comma-separated MCP servers to register. Default:
                       tilth,context7. Choices: tilth, context7, tavily,
                       code-review-graph, none
  --skip-mcp           Same as --mcp none.
  --skip-tools         Skip CLI tool installs (useful for MCP-only runs).
  --harness <name>     Harness to register skills + MCP servers with.
                       Default: claude-code. Other values include cursor,
                       vscode, codex, gemini, zed, copilot.
  --no-edit            Register tilth without the --edit capability.
  --dry-run            Print what would happen without changing anything.
  -h, --help           Show this help.

Environment:
  EC_BREW   EC_GH      Override the brew / gh binaries (used by tests).
  EC_CARGO  EC_NPM     Override the cargo / npm binaries used to install tilth.
  EC_TILTH  EC_CLAUDE  Override the tilth / claude binaries (used by tests).
  EC_NPX               Override npx (used to launch context7 / tavily MCP).
  EC_UV     EC_PIPX    Override uv / pipx for code-review-graph install.
  EC_PIP    EC_CRG     Override pip / code-review-graph binaries.
USAGE
}

# OS guard. Returns 0 on macOS, 1 otherwise.
ec_detect_os() {
    case "$(uname -s)" in
        Darwin) return 0 ;;
        *)      return 1 ;;
    esac
}

ec_cmd_exists() {
    command -v "$1" >/dev/null 2>&1
}

ec_brew() {
    "${EC_BREW:-brew}" "$@"
}

# Verify Homebrew is installed; print install hint and fail otherwise.
ec_ensure_homebrew() {
    if ec_cmd_exists "${EC_BREW:-brew}"; then
        return 0
    fi
    ec_err "Homebrew is required but was not found."
    ec_err "Install it from https://brew.sh and re-run this script."
    return 1
}

# Returns 0 if every comma-separated token in $1 is in the space-separated
# list $2. Prints the offending token to stderr otherwise.
ec_validate_selection() {
    local list="$1" allowed="$2" token
    local IFS=,
    for token in $list; do
        case " $allowed " in
            *" $token "*) ;;
            *)
                ec_err "Unknown selection: $token"
                return 1
                ;;
        esac
    done
}

# Idempotently install one brew formula. Returns 0 if installed (or already
# present), 1 if brew failed. Honors $EC_DRY_RUN.
ec_brew_install_if_missing() {
    local tool="$1"
    local binary
    binary="$(ec_tool_binary "$tool")"

    if ec_cmd_exists "$binary"; then
        ec_log "$tool: already installed ($binary on PATH)"
        return 0
    fi

    if [[ "${EC_DRY_RUN:-0}" == "1" ]]; then
        ec_log "$tool: would run 'brew install $tool'"
        return 0
    fi

    ec_log "$tool: installing via 'brew install $tool'"
    ec_brew install "$tool"
}

# tilth has no Homebrew formula. Install via cargo (preferred — native
# binary) or fall back to 'npm install -g tilth' (jahala/tilth ships a
# proper bin entry on npm). Errors out clearly if neither is available.
ec_install_tilth() {
    local cargo="${EC_CARGO:-cargo}"
    local npm="${EC_NPM:-npm}"

    if ec_cmd_exists tilth; then
        ec_log "tilth: already installed (tilth on PATH)"
        return 0
    fi

    if ec_cmd_exists "$cargo"; then
        if [[ "${EC_DRY_RUN:-0}" == "1" ]]; then
            ec_log "tilth: would run '$cargo install tilth'"
            return 0
        fi
        ec_log "tilth: installing via 'cargo install tilth'"
        "$cargo" install tilth
        return $?
    fi

    if ec_cmd_exists "$npm"; then
        if [[ "${EC_DRY_RUN:-0}" == "1" ]]; then
            ec_log "tilth: would run '$npm install -g tilth' (cargo not found)"
            return 0
        fi
        ec_log "tilth: installing via 'npm install -g tilth' (cargo not found)"
        "$npm" install -g tilth
        return $?
    fi

    ec_err "tilth: needs cargo (Rust) or npm (Node 18+); neither was found."
    ec_err "Install Rust from https://rustup.rs or Node.js from https://nodejs.org and re-run."
    return 1
}

# Install every tool in the comma-separated list. tilth is routed through
# ec_install_tilth; everything else goes through brew.
ec_install_tools() {
    local list="$1" tool
    local IFS=,
    for tool in $list; do
        case "$tool" in
            tilth) ec_install_tilth ;;
            *)     ec_brew_install_if_missing "$tool" ;;
        esac
    done
}

# Register a single MCP server with the chosen harness.
ec_install_mcp() {
    local server="$1" harness="$2" with_edit="$3"
    case "$server" in
        tilth)
            ec_install_mcp_tilth "$harness" "$with_edit"
            ;;
        context7)
            ec_install_mcp_context7 "$harness"
            ;;
        tavily)
            ec_install_mcp_tavily "$harness"
            ;;
        code-review-graph)
            ec_install_mcp_crg "$harness"
            ;;
        none)
            ec_log "MCP: skipping (none selected)"
            ;;
        *)
            ec_err "Unknown MCP server: $server"
            return 1
            ;;
    esac
}

ec_install_mcp_tilth() {
    local harness="$1" with_edit="$2"
    # Reset IFS — ec_install_mcp_list sets it to ',' which would leak into
    # the dry-run "${args[*]}" expansion below via dynamic scoping.
    local IFS=$' \t\n'
    local tilth="${EC_TILTH:-tilth}"
    if ! ec_cmd_exists "$tilth"; then
        ec_warn "tilth MCP: tilth CLI is not installed; include 'tilth' in --tools first."
        return 1
    fi
    local args=(install "$harness")
    if [[ "$with_edit" == "1" ]]; then
        args+=(--edit)
    fi
    if [[ "${EC_DRY_RUN:-0}" == "1" ]]; then
        ec_log "tilth MCP: would run '$tilth ${args[*]}'"
        return 0
    fi
    ec_log "tilth MCP: registering with $harness"
    "$tilth" "${args[@]}"
}

ec_install_mcp_context7() {
    local harness="$1"
    local claude="${EC_CLAUDE:-claude}"
    local npx="${EC_NPX:-npx}"
    if [[ "$harness" != "claude-code" ]]; then
        ec_warn "context7 MCP: only claude-code is auto-registered; configure $harness manually."
        return 0
    fi
    if ! ec_cmd_exists "$claude"; then
        ec_warn "context7 MCP: claude CLI not found; install Claude Code first."
        return 1
    fi
    if [[ "${EC_DRY_RUN:-0}" == "1" ]]; then
        ec_log "context7 MCP: would run '$claude mcp add context7 -- $npx -y @upstash/context7-mcp@latest'"
        return 0
    fi
    ec_log "context7 MCP: registering with claude-code"
    "$claude" mcp add context7 -- "$npx" -y @upstash/context7-mcp@latest
}

ec_install_mcp_tavily() {
    local harness="$1"
    local claude="${EC_CLAUDE:-claude}"
    local npx="${EC_NPX:-npx}"
    if [[ "$harness" != "claude-code" ]]; then
        ec_warn "tavily MCP: only claude-code is auto-registered; configure $harness manually."
        return 0
    fi
    if ! ec_cmd_exists "$claude"; then
        ec_warn "tavily MCP: claude CLI not found; install Claude Code first."
        return 1
    fi
    if [[ -z "${TAVILY_API_KEY:-}" ]]; then
        ec_warn "tavily MCP: TAVILY_API_KEY is not set; the server will fail until you set one."
    fi
    if [[ "${EC_DRY_RUN:-0}" == "1" ]]; then
        ec_log "tavily MCP: would run '$claude mcp add tavily -- $npx -y tavily-mcp'"
        return 0
    fi
    ec_log "tavily MCP: registering with claude-code"
    "$claude" mcp add tavily -- "$npx" -y tavily-mcp
}

# Install the code-review-graph CLI with the local sentence-transformers
# embeddings extra so 'code-review-graph embed' works out of the box.
# Prefers an isolated tool install (uv → pipx) so we don't poke at the
# system Python. Falls back to 'pip install --user' with a warning so it
# still works on minimal boxes.
#
# The package spec is quoted because '[embeddings]' contains shell glob
# characters; inside an array invocation the quoting is implicit, but the
# dry-run log line uses a literal single-quoted form to match.
ec_install_crg_cli() {
    local uv="${EC_UV:-uv}"
    local pipx="${EC_PIPX:-pipx}"
    local pip="${EC_PIP:-pip}"
    local spec='code-review-graph[embeddings]'

    if ec_cmd_exists "$uv"; then
        if [[ "${EC_DRY_RUN:-0}" == "1" ]]; then
            ec_log "code-review-graph: would run '$uv tool install $spec'"
            return 0
        fi
        ec_log "code-review-graph: installing via '$uv tool install $spec'"
        "$uv" tool install "$spec"
        return $?
    fi

    if ec_cmd_exists "$pipx"; then
        if [[ "${EC_DRY_RUN:-0}" == "1" ]]; then
            ec_log "code-review-graph: would run '$pipx install $spec'"
            return 0
        fi
        ec_log "code-review-graph: installing via '$pipx install $spec'"
        "$pipx" install "$spec"
        return $?
    fi

    if ec_cmd_exists "$pip"; then
        ec_warn "code-review-graph: uv/pipx not found; falling back to 'pip install --user'."
        if [[ "${EC_DRY_RUN:-0}" == "1" ]]; then
            ec_log "code-review-graph: would run '$pip install --user $spec'"
            return 0
        fi
        ec_log "code-review-graph: installing via '$pip install --user $spec'"
        "$pip" install --user "$spec"
        return $?
    fi

    ec_err "code-review-graph: needs uv, pipx, or pip; none found."
    ec_err "Install uv from https://docs.astral.sh/uv or pipx from https://pipx.pypa.io and re-run."
    return 1
}

ec_install_mcp_crg() {
    local harness="$1"
    local crg="${EC_CRG:-code-review-graph}"
    if ! ec_cmd_exists "$crg"; then
        ec_install_crg_cli || return 1
        # 'pip install --user' and 'pipx ensurepath' can leave the binary
        # in a directory that isn't on PATH yet (the pipx user bin or the
        # Python user-site bin). Re-check explicitly so the user gets a
        # targeted hint instead of a generic "command not found" later.
        if [[ "${EC_DRY_RUN:-0}" != "1" ]] && ! ec_cmd_exists "$crg"; then
            ec_err "code-review-graph: install succeeded but '$crg' is not on PATH."
            ec_err "Add the install location to PATH (run 'pipx ensurepath', or"
            ec_err "add the Python user-site bin dir for pip --user) and re-run."
            return 1
        fi
    fi
    if [[ "${EC_DRY_RUN:-0}" == "1" ]]; then
        ec_log "code-review-graph: would run '$crg install --platform $harness'"
        return 0
    fi
    ec_log "code-review-graph: registering with $harness"
    "$crg" install --platform "$harness"
}

ec_install_mcp_list() {
    local list="$1" harness="$2" with_edit="$3" server
    local IFS=,
    for server in $list; do
        ec_install_mcp "$server" "$harness" "$with_edit"
    done
}

# Discover the live skill list by listing skills/ via the GitHub contents
# API. Prints one skill name per line on success; on failure (network,
# rate limit, private repo) returns non-zero with empty stdout and the
# caller falls back to EC_FALLBACK_SKILLS.
ec_discover_skills() {
    local gh="$1"
    "$gh" api "repos/${EC_SKILL_REPO}/contents/skills" \
        --jq '.[] | select(.type == "dir") | .name' 2>/dev/null
}

# Install the easy-cheese skill set into the picked harness via 'gh skill'.
# User scope so they live alongside the user's other skills, not committed
# into the project. Requires gh to be authenticated.
#
# `gh skill install` does not support an --all flag, so we discover the
# live skill list via 'gh api ... contents/skills' and call gh once per
# skill with --force for idempotent re-runs. If discovery fails we fall
# back to EC_FALLBACK_SKILLS so the installer still does something useful
# offline. Per-skill install failures are warned and tracked but do not
# abort the rest of the loop. Dry-run skips discovery and uses the
# embedded list for predictable, network-free output.
ec_install_skills() {
    local harness="$1"
    local gh="${EC_GH:-gh}"
    if ! ec_cmd_exists "$gh"; then
        ec_warn "easy-cheese skills: gh CLI not found; skipping. Add 'gh' to --tools first."
        return 0
    fi

    local skills="$EC_FALLBACK_SKILLS"
    if [[ "${EC_DRY_RUN:-0}" != "1" ]]; then
        if ! "$gh" auth status >/dev/null 2>&1; then
            ec_warn "easy-cheese skills: gh is not authenticated. Run 'gh auth login' and re-run."
            return 1
        fi
        local discovered
        if discovered="$(ec_discover_skills "$gh")" && [[ -n "$discovered" ]]; then
            skills="$discovered"
        else
            ec_warn "easy-cheese skills: could not list skills via gh api; using embedded fallback list."
        fi
    fi

    local skill rc=0
    for skill in $skills; do
        if [[ "${EC_DRY_RUN:-0}" == "1" ]]; then
            ec_log "easy-cheese skills: would run '$gh skill install $EC_SKILL_REPO $skill --agent $harness --scope user --force'"
            continue
        fi
        ec_log "easy-cheese skills: installing $skill into $harness (user scope)"
        if ! "$gh" skill install "$EC_SKILL_REPO" "$skill" --agent "$harness" --scope user --force; then
            ec_warn "easy-cheese skills: failed to install $skill"
            rc=1
        fi
    done
    return $rc
}

# Parse argv into the EC_* config variables. Echoes nothing on success;
# echoes an error and returns non-zero on failure.
ec_parse_args() {
    EC_TOOLS="$EC_DEFAULT_TOOLS"
    EC_TOOLS="${EC_TOOLS// /,}"
    EC_MCP="$EC_DEFAULT_MCP"
    EC_MCP="${EC_MCP// /,}"
    EC_HARNESS="claude-code"
    EC_WITH_EDIT="1"
    EC_DRY_RUN="${EC_DRY_RUN:-0}"
    EC_SKIP_TOOLS="0"
    EC_DO_HELP="0"

    while [[ $# -gt 0 ]]; do
        case "$1" in
            --tools)
                shift
                [[ $# -gt 0 ]] || { ec_err "--tools requires a value"; return 2; }
                EC_TOOLS="$1"
                ;;
            --tools=*)
                EC_TOOLS="${1#*=}"
                ;;
            --mcp)
                shift
                [[ $# -gt 0 ]] || { ec_err "--mcp requires a value"; return 2; }
                EC_MCP="$1"
                ;;
            --mcp=*)
                EC_MCP="${1#*=}"
                ;;
            --skip-mcp)
                EC_MCP="none"
                ;;
            --skip-tools)
                EC_SKIP_TOOLS="1"
                ;;
            --harness)
                shift
                [[ $# -gt 0 ]] || { ec_err "--harness requires a value"; return 2; }
                EC_HARNESS="$1"
                ;;
            --harness=*)
                EC_HARNESS="${1#*=}"
                ;;
            --no-edit)
                EC_WITH_EDIT="0"
                ;;
            --dry-run)
                EC_DRY_RUN="1"
                ;;
            -h|--help)
                EC_DO_HELP="1"
                ;;
            --)
                shift
                break
                ;;
            -*)
                ec_err "Unknown option: $1"
                return 2
                ;;
            *)
                ec_err "Unexpected positional argument: $1"
                return 2
                ;;
        esac
        shift
    done

    ec_validate_selection "$EC_TOOLS" "$EC_KNOWN_TOOLS" || return 2
    ec_validate_selection "$EC_MCP" "tilth context7 tavily code-review-graph none" || return 2
}

ec_main() {
    ec_parse_args "$@" || return $?

    if [[ "$EC_DO_HELP" == "1" ]]; then
        ec_usage
        return 0
    fi

    if ! ec_detect_os; then
        ec_err "easy-cheese installer currently supports macOS only."
        ec_err "Detected: $(uname -s). See README for manual install on other platforms."
        return 1
    fi

    if [[ "$EC_SKIP_TOOLS" != "1" ]]; then
        ec_ensure_homebrew || return 1
        ec_install_tools "$EC_TOOLS"
    fi

    ec_install_skills "$EC_HARNESS"

    if [[ "$EC_MCP" != "none" ]]; then
        ec_install_mcp_list "$EC_MCP" "$EC_HARNESS" "$EC_WITH_EDIT"
    fi

    ec_log "Done. Restart your harness so skills, MCP servers, and PATH changes take effect."
}

# Only run main when executed directly, not when sourced (so tests can load
# functions individually). strict-mode is scoped here so sourcing the file
# does not flip -e/-u/-o pipefail in the caller's shell.
if [[ "${BASH_SOURCE[0]:-}" == "${0}" ]]; then
    set -euo pipefail
    ec_main "$@"
fi
