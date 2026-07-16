set dotenv-load := true

# Keep pytest hermetic: only load plugins the suite declares, never whatever
# third-party pytest plugins happen to be globally installed. Without this a
# stray global plugin (e.g. pytest-httpx) can crash collection on a missing
# transitive dep. CI installs a clean env so it is unaffected either way.
export PYTEST_DISABLE_PLUGIN_AUTOLOAD := "1"

# List all available commands
@default:
    just --list

# Run all tests (skill validators + melt + shared + fan-out suites + bash install tests + fan-out bats + JS)
test:
    python3 .github/scripts/test_validate_skills.py -v
    python3 .github/scripts/validate_skills.py
    python3 .github/scripts/validate_wiki.py
    python3 -m pytest tests/python -q
    python3 -m pytest tests/shared/python -q
    python3 -m pytest tests/fanout/python -q
    python3 -m pytest tests/hard-cheese/python -q
    python3 -m pytest tests/pasteurize/python -q
    node --test 'tests/js/**/*.test.mjs'
    bats tests/bash/test_install.bats
    bats tests/fanout/bash/test_pr_plan_to_branches.bats

# Build self-contained .pyz bundles for shared-consuming skills (CI rebuilds on every push to main)
bundle:
    python3 scripts/build_pyz.py

# Preview the exact tree a release ships (skills + .pyz only, no sources)
release-preview:
    python3 scripts/stage_release.py --out .release-preview
    @echo "Staged release tree at .release-preview — inspect with: find .release-preview -type f"

# Lint shell scripts
lint-sh:
    shellcheck scripts/install.sh

# Fix markdown formatting issues
lint-md-fix:
    markdownlint-cli2 --fix "skills/**/*.md" "*.md"

# Verify markdown (no autofix)
lint-md:
    markdownlint-cli2 "skills/**/*.md" "*.md"

# Fix YAML formatting issues
lint-yaml-fix:
    yamlfmt .

# Verify YAML formatting
lint-yaml:
    yamllint -c .yamllint.yml .

# Autofix Python lint with ruff (via uvx, no global install needed)
lint-py-fix:
    uvx ruff check --fix .

# Full local check with autofixes
check: lint-md-fix lint-yaml-fix lint-yaml lint-py-fix lint-sh test docs-build

# CI-mode verification (no autofixes)
ci: lint-md lint-yaml lint-sh test docs-build

# Install docs build dependencies
docs-install:
    corepack pnpm install --frozen-lockfile
    pip install --no-cache-dir pyyaml==6.0.2

# Build the docs site (output: dist/)
docs-build: docs-install
    corepack pnpm run docs:build

# Serve docs locally on http://localhost:4321 with live reload
docs-serve: docs-install
    corepack pnpm run docs:dev
