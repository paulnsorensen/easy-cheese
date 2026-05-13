---
applyTo: ".github/scripts/**/*.py,tests/python/**/*.py"
---

# Python review checklist (skill validators + melt script tests)

Two Python surfaces live in this repo:

- `.github/scripts/` — CI validators (`validate_skills.py` + `test_validate_skills.py`).
  These run on `python3` from the GitHub Actions runner with `pyyaml` as
  the only third-party dependency. No virtualenv, no `uv`.
- `tests/python/` — pytest suite covering the `melt` skill's helper
  scripts (`conflict_pick`, `conflict_summary`, `batch_resolve`, etc.).
  Runs under `pytest` with stdlib-style fixtures via `conftest.py`.

## Hard rules

- **Dependencies are pinned in `validate.yml`.** The only allowed
  third-party imports are `pyyaml` (validators) and `pytest` (tests). Push
  back on PRs that pull in `requests`, `pydantic`, `pandas`, etc. — every
  new dep means a bootstrap step in CI and another supply-chain edge.
- **Python 3.12 baseline.** CI pins `python-version: "3.12"`. Don't reach
  for 3.13+ features without updating `validate.yml` first; don't write
  3.8-compatible code "to be safe" either — the runner is fixed.
- **No filesystem writes from validators.** `.github/scripts/` files read
  and report; they never mutate the tree. A PR that adds autofix logic
  belongs in a separate skill or script, not in `validate_skills.py`.
- **Exit-code propagation is load-bearing.** Validators and pytest must
  exit non-zero on failure, or CI silently passes. `except Exception:`
  without re-raising or `sys.exit(1)` is a bug, not a style issue.

## What to flag

- New top-level functions over 40 lines — decompose.
- Bare `except:` or `except Exception:` that swallows errors in either
  surface. Validators must fail loud; tests must surface failures cleanly.
- Tests in `tests/python/*.py` or `test_validate_skills.py` that don't
  actually assert on observable behavior — `assert True` after a
  `try/except` block is not a test.
- pytest tests that depend on filesystem state outside `tmp_path` or
  network access. Both make CI flaky.
- Hard-coded paths that escape the repo root (e.g. `/Users/...`,
  `os.path.expanduser("~/Dev/...")`). Use `Path(__file__).resolve()` or
  pytest's `tmp_path` / `monkeypatch.chdir`.

## What not to flag

- Missing type hints on internal helpers. Annotate function boundaries; let
  inference handle the rest.
- Missing docstrings on private functions with clear names.
- f-string vs `.format()` style preferences.
- Anything `ruff` or `mypy` would catch — this repo doesn't run them, and
  introducing them is a separate decision.
- pytest fixtures defined in `conftest.py` instead of inline. That's the
  conventional location and reviewers shouldn't relitigate it.
