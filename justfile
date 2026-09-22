set dotenv-load := true
# Includes requirements-build.txt so tests/python/test_pyz_bundle.py runs its
# bundle integration seam instead of skipping it.
python := "uv run --no-project --with-requirements requirements/runtime.txt --with-requirements requirements-build.txt --with pip==26.2.1 --with pytest==9.0.3 --with pytest-xdist==3.8.0 --with pyyaml==6.0.2 python3"

# Keep pytest hermetic: only load plugins the suite declares, never whatever
# third-party pytest plugins happen to be globally installed. Without this a
# stray global plugin (e.g. pytest-httpx) can crash collection on a missing
# transitive dep. CI installs a clean env so it is unaffected either way.
export PYTEST_DISABLE_PLUGIN_AUTOLOAD := "1"

# Corepack prompts before it fetches a pinned pnpm. The `test` recipe backgrounds
# its corepack checks, and a background job in a non-interactive shell has no
# stdin, so an unanswerable prompt would fail the run instead of provisioning.
export COREPACK_ENABLE_DOWNLOAD_PROMPT := "0"

# List all available commands
@default:
    just --list

# Run all tests (skill validators + melt + shared + fan-out + wheypoint suites + bash + JS)
test:
    #!/usr/bin/env bash
    set -euo pipefail
    # Job control puts each background job in its own process group, so cleanup
    # can signal the whole tree rather than only the `just` child.
    set -m

    # Read the worker count as a value, never as recipe text. `set dotenv-load`
    # makes a repo-local dotenv file an environment source, and a just
    # interpolation would splice that value into this script as shell code.
    pytest_workers="${PYTEST_WORKERS:-auto}"
    if [[ ! $pytest_workers =~ ^(auto|logical|[0-9]+)$ ]]; then
        printf 'PYTEST_WORKERS must be auto, logical, or a worker count; got %q\n' \
            "$pytest_workers" >&2
        exit 2
    fi

    # Cheap validators first so an obvious break fails fast.
    {{python}} .github/scripts/test_validate_skills.py -v
    {{python}} .github/scripts/test_validate_wiki.py
    {{python}} .github/scripts/validate_skills.py
    {{python}} .github/scripts/validate_wiki.py
    {{python}} scripts/render_generated_regions.py --check

    # Build every bundle once; the xdist workers reuse it instead of each
    # rebuilding the whole set (see tests/python/conftest.py prebuilt_bundle_dir).
    prebuilt_pyz_dir="$(mktemp -d)"
    export EASY_CHEESE_PREBUILT_PYZ="$prebuilt_pyz_dir"

    background_pids=()
    # Reap every background check on every exit path, including an early `set -e`
    # exit from a foreground suite, so no orphan survives the recipe. The trap
    # only reaps; the explicit `wait` calls below own failure propagation.
    cleanup() {
        local pid
        for pid in ${background_pids[@]+"${background_pids[@]}"}; do
            kill -- "-$pid" 2>/dev/null || kill "$pid" 2>/dev/null || true
            wait "$pid" 2>/dev/null || true
        done
        rm -rf "$prebuilt_pyz_dir"
    }
    trap cleanup EXIT

    {{python}} scripts/build_pyz.py --out-dir "$EASY_CHEESE_PREBUILT_PYZ"

    # The pytest suites are latency-bound (subprocess-heavy) and leave cores
    # idle, so run the CPU-bound independent checks (pnpm build, cargo) alongside
    # them. Failures still fail the recipe via the waited exit codes below.
    just test-mold-review &
    mold_review_pid=$!
    background_pids+=("$mold_review_pid")
    just test-skill-overlap &
    skill_overlap_pid=$!
    background_pids+=("$skill_overlap_pid")

    {{python}} -m pytest tests/python -q -p xdist -n "$pytest_workers" --ignore=tests/python/test_mold_cook_browser_workflow.py
    {{python}} -m pytest tests/shared/python -q -p xdist -n "$pytest_workers"
    {{python}} -m pytest tests/fanout/python -q -p xdist -n "$pytest_workers"
    {{python}} -m pytest tests/schemas/python -q -p xdist -n "$pytest_workers"
    {{python}} -m pytest tests/hard-cheese/python -q
    {{python}} -m pytest tests/pasteurize/python -q -p xdist -n "$pytest_workers"
    {{python}} -m pytest tests/wheypoint/python -q -p xdist -n "$pytest_workers"
    node --test 'tests/js/**/*.test.mjs'
    bats tests/bash/test_install.bats
    uv run --no-project --with-requirements requirements/runtime.txt --with pip==26.2.1 --with pyyaml==6.0.2 bats tests/fanout/bash/test_pr_plan_to_branches.bats

    # Surface any failure from the concurrent checks. Wait for both before
    # failing so a second failure is not masked by an early exit.
    mold_review_status=0
    wait "$mold_review_pid" || mold_review_status=$?
    skill_overlap_status=0
    wait "$skill_overlap_pid" || skill_overlap_status=$?
    background_pids=()
    if [[ $mold_review_status -ne 0 || $skill_overlap_status -ne 0 ]]; then
        printf 'test-mold-review exited %d; test-skill-overlap exited %d\n' \
            "$mold_review_status" "$skill_overlap_status" >&2
        exit 1
    fi

# Build and exercise the development-only Mold review browser harness
test-mold-review:
    corepack pnpm --dir frontend/mold-review run build
    corepack pnpm --dir frontend/mold-review run test

# Run the real Mold-to-Cook browser workflow in its isolated fixture package.
# Dependency and Chromium provisioning intentionally stay outside `test`.
playwright_cache := justfile_directory() + "/.context/playwright"
browser_fixture := justfile_directory() + "/tests/fixtures/mold_cook_browser"

test-workflow-browser:
    mkdir -p "{{playwright_cache}}"
    cp "{{browser_fixture}}/package.json" "{{browser_fixture}}/pnpm-lock.yaml" "{{playwright_cache}}/"
    corepack pnpm --dir "{{playwright_cache}}" install --frozen-lockfile
    PLAYWRIGHT_BROWSERS_PATH="{{playwright_cache}}/browsers" corepack pnpm --dir "{{playwright_cache}}" exec playwright install chromium
    MOLD_COOK_BROWSER=1 MOLD_COOK_BROWSER_NODE_MODULES="{{playwright_cache}}/node_modules" PLAYWRIGHT_BROWSERS_PATH="{{playwright_cache}}/browsers" {{python}} -m pytest tests/python/test_mold_cook_browser_workflow.py -q
# Run model-free overlap analyzer tests (never fetches model artifacts)
test-skill-overlap:
    cargo test --manifest-path tools/skill-overlap/Cargo.toml

# Build one self-contained Shiv .pyz archive per Python skill
bundle:
    uv run --no-project --with-requirements requirements/runtime.txt --with-requirements requirements-build.txt python3 scripts/build_pyz.py

# Write every generated runtime source the bundle build checks for staleness
update-generated:
    uv run --no-project --with-requirements requirements/runtime.txt --with-requirements requirements-build.txt python3 scripts/build_pyz.py --write-generated

# Preview the exact tree a release ships (skills + .pyz only, no sources)
release-preview:
    python3 scripts/stage_release.py --out .release-preview
    @echo "Staged release tree at .release-preview — inspect with: find .release-preview -type f"

# Lint shell scripts
lint-sh:
    shellcheck scripts/install.sh

# Fix markdown formatting issues
lint-md-fix:
    markdownlint-cli2 --fix "skills/**/*.md" ".agents/**/*.md" "*.md"

# Verify markdown (no autofix)
lint-md:
    markdownlint-cli2 "skills/**/*.md" ".agents/**/*.md" "*.md"

# Fix YAML formatting issues
lint-yaml-fix:
    yamlfmt .

# Verify YAML formatting
lint-yaml:
    yamllint -c .yamllint.yml .

# Autofix Python lint with ruff (via uvx, no global install needed)
lint-py-fix:
    uvx ruff check --fix .

# Create/refresh the venv basedpyright resolves imports against
typecheck-install:
    uv venv --quiet --allow-existing --python 3.12 .venv-typing
    uv pip install --quiet --require-hashes --python .venv-typing/bin/python --requirement requirements/typing.txt

# Type-check all Python (recommended tier fails on warnings too)
typecheck: typecheck-install
    uvx basedpyright@1.39.10

# Check for unused Python code with owner-qualified Vulture classifier
lint-py-dead-code *paths="src scripts .github/scripts tests":
    #!/usr/bin/env bash
    set -uo pipefail
    uvx --from vulture==2.16 python3 scripts/check_dead_code.py {{paths}}
    status=$?
    case "$status" in
      0) ;;
      3) echo "dead code found" >&2 ;;
      *) echo "could not analyse: check_dead_code.py exited $status" >&2 ;;
    esac
    exit "$status"


# Regenerate .github/skill-budgets.json (size/structure ratchet) after shrinking a skill
update-skill-budgets:
    python3 .github/scripts/validate_skills.py --write-budgets

# Verify committed .pyz bundles match the staged index (local/pre-commit)
check-bundles:
    python3 scripts/check_bundles.py --against index

# Verify committed .pyz bundles match HEAD after a fresh rebuild (CI)
check-bundles-ci: bundle
    python3 scripts/check_bundles.py --against head

# Full local check with autofixes
check: lint-md-fix lint-yaml-fix lint-yaml lint-py-fix lint-sh lint-py-dead-code typecheck test docs-build check-bundles

# CI-mode verification (no autofixes)
ci: lint-md lint-yaml lint-sh lint-py-dead-code typecheck test docs-build check-bundles-ci

# Install docs build dependencies
docs-install:
    corepack pnpm install --frozen-lockfile
    python3 -m venv --clear .venv
    .venv/bin/python -m pip install --no-cache-dir pyyaml==6.0.2

# Build the docs site (output: dist/)
docs-build: docs-install
    PATH="$PWD/.venv/bin:$PATH" corepack pnpm run docs:build

# Serve docs locally on http://localhost:4321 with live reload
docs-serve: docs-install
    PATH="$PWD/.venv/bin:$PATH" corepack pnpm run docs:dev
