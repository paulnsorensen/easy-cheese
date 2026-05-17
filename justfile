set dotenv-load := true

# List all available commands
@default:
    just --list

# Run all tests (skill validators + melt pytest suite + cheese-factory suite + bash install tests + cheese-factory bats)
test:
    python3 .github/scripts/test_validate_skills.py -v
    python3 .github/scripts/validate_skills.py
    python3 -m pytest tests/python -q
    python3 -m pytest tests/cheese-factory/python -q
    bats tests/bash/test_install.bats
    bats tests/cheese-factory/bash/test_pr_plan_to_branches.bats

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

# Full local check with autofixes
check: lint-md-fix lint-yaml-fix lint-yaml lint-sh test docs-build

# CI-mode verification (no autofixes)
ci: lint-md lint-yaml lint-sh test docs-build

# Install docs build dependencies into a local venv
docs-install:
    python3 -m venv .venv
    .venv/bin/python -m pip install -r docs/requirements.txt

# Build the docs site (output: site/)
docs-build: docs-install
    .venv/bin/mkdocs build --strict

# Serve docs locally on http://localhost:8000 with live reload
docs-serve: docs-install
    .venv/bin/mkdocs serve
