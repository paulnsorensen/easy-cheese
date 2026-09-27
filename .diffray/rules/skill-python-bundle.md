---
name: skill-python-bundle
description: Enforce the easy-cheese skill Python bundle doctrine
patterns:
  - "skills/**"
agent: general
---

Enforce the skill Python bundle doctrine (see `AGENTS.md` and
`.hallouminate/wiki/architecture/skill-python-bundle-doctrine.md`).

Flag changes that:

1. Add hand-written Python (`.py`) anywhere under `skills/`. Runtime Python
   must live under `src/`; `skills/<skill>/scripts/` may contain only the
   generated wedge launcher `<skill>` and its lock `<skill>.wedge.json`.
2. Edit a launcher by hand, commit a `.pyz` archive, or change a lock without
   the `src/`, `pyproject.toml`, `uv.lock`, or `wedge.toml` change that
   `just wedge-lock` regenerated it from.
3. Make a skill invoke anything other than its own
   `skills/<skill>/scripts/<skill>` launcher: never loose source, `common.pyz`,
   repository automation, or another skill's launcher.
4. Ship a skill with more than one launcher, or ship a launcher for a skill
   that executes no Python.
5. Introduce archive dependencies that are not pure-Python and zip-importable:
   native extensions, platform-specific libraries, required external
   executables, runtime package installation, downloads other than the
   launcher's fetch of its own locked archive, or caller-managed extraction.

Only report actual violations present in the diff. Do NOT report positive
observations or "no issues found" messages.
