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
    shellcheck scripts/install.sh skills/cheese-factory/scripts/pr_plan_to_branches.sh

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
check: lint-md-fix lint-yaml-fix lint-yaml lint-sh test

# CI-mode verification (no autofixes)
ci: lint-md lint-yaml lint-sh test
