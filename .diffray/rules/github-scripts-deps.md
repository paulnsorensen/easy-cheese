---
name: github-scripts-deps
description: Restrict third-party deps in .github/scripts Python validators
patterns:
  - ".github/scripts/**/*.py"
agent: general
---

Python validators under `.github/scripts/` may use only the standard library
plus `pyyaml` and `pytest` as third-party dependencies (see
`.github/instructions/python.instructions.md`).

Flag any import of a third-party package other than `yaml` (pyyaml) or
`pytest`. Standard-library imports are always allowed.

Only report actual violations present in the diff. Do NOT report positive
observations or "no issues found" messages.
