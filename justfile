set dotenv-load := true
# Includes requirements-build.txt so tests/python/test_pyz_bundle.py runs its
# bundle integration seam instead of skipping it.
python := "uv run --no-project --with-requirements requirements/runtime.txt --with-requirements requirements-build.txt --with pip==26.2.1 --with pytest==9.0.3 --with pyyaml==6.0.2 python3"

# Keep pytest hermetic: only load plugins the suite declares, never whatever
# third-party pytest plugins happen to be globally installed. Without this a
# stray global plugin (e.g. pytest-httpx) can crash collection on a missing
# transitive dep. CI installs a clean env so it is unaffected either way.
export PYTEST_DISABLE_PLUGIN_AUTOLOAD := "1"

# List all available commands
@default:
    just --list

# Run all tests (skill validators + melt + shared + fan-out + wheypoint suites + bash + JS)
test:
    {{python}} .github/scripts/test_validate_skills.py -v
    {{python}} .github/scripts/test_validate_wiki.py
    {{python}} .github/scripts/validate_skills.py
    {{python}} .github/scripts/validate_wiki.py
    {{python}} scripts/render_generated_regions.py --check
    {{python}} -m pytest tests/python -q
    {{python}} -m pytest tests/shared/python -q
    {{python}} -m pytest tests/fanout/python -q
    {{python}} -m pytest tests/schemas/python -q
    {{python}} -m pytest tests/hard-cheese/python -q
    {{python}} -m pytest tests/pasteurize/python -q
    {{python}} -m pytest tests/wheypoint/python -q
    node --test 'tests/js/**/*.test.mjs'
    bats tests/bash/test_install.bats
    uv run --no-project --with-requirements requirements/runtime.txt --with pip==26.2.1 --with pyyaml==6.0.2 bats tests/fanout/bash/test_pr_plan_to_branches.bats
    just test-skill-overlap

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
