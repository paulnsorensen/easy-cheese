# Melt Area Review

## Verdict

reject

## Blocker

- **The format guide skips supported structural merges.** `skills/melt/references/cascade-stages.md:9-10` classifies shell, YAML, and JSON as unsupported formats. `mergiraf languages` lists Bash, YAML, and JSON. `src/easy_cheese/skills/melt/conflict_summary.py:67-74` also checks structural support before it recommends side selection. Fix: Remove the static list. Use the command's `mergiraf_supported` result to select the next command.
- **The Melt handoff violates the shared gate contract.** `skills/melt/SKILL.md:197-205` lists three prose options. It omits IDs, a prompt, a recommendation, `multi`, and executable action fields. `skills/cheese/references/handoff-gate.md:56-75` requires these fields. `skills/cheese/references/handoff-gate.md:195-211` also requires the standard tail for a richer decision. Fix: Define one structured Melt gate. Define safe `Plate it` behavior before you add the standard tail.

## High

- **The cascade depends on hidden Git configuration.** `skills/melt/SKILL.md:29-30,144-157` claims rerere and kdiff3 stages. It runs only rerere inspection commands and a generic `git mergetool`. Those commands do not guarantee either stage when host settings differ. This workstation sets `rerere.enabled=true` and `merge.tool=kdiff3`, so its settings hide the defect. Fix: Invoke `git rerere` and `git mergetool --tool=kdiff3`. Otherwise, add a preflight that checks and explains both settings.

## Medium

none

## Low

- **The zdiff3 claim is too broad.** `skills/melt/SKILL.md:192` says every script handles base markers. `detect-squash-residue` does not read conflicts, and `lockfile-resolve` uses index stages. Fix: Name only commands that parse conflict markers.

## Simplifications

- Use `conflict-summary` as the only source for format support.
- Replace the Handoff prose list with one structured gate record.
- Use one preflight for the rerere and kdiff3 requirements.
- Keep the five command wrappers. The manifest needs decorated callables and lazy imports.

## Edge check

| Edge | State | Evidence |
| --- | --- | --- |
| `melt -> shared`: command declarations | ok | `src/easy_cheese/skills/melt/commands.py:7-59` uses `bundle_command` and `derive_command`. Their definitions exist at `src/easy_cheese/shared/bundle_commands.py:61-83`. |
| `melt -> shared`: command dispatch | ok | `src/easy_cheese/skills/melt/commands.py:62-63` calls `dispatch`. The shared dispatcher exists at `src/easy_cheese/shared/bundle_commands.py:138-154`. The bundle help lists all five commands. |
| `melt -> cheese`: code inspection | ok | `skills/melt/SKILL.md:18-22,133-135` follows `skills/cheese/references/code-intelligence-routing.md:3-38`. |
| `melt -> cheese`: handoff selection | broken | `skills/melt/SKILL.md:197-205` omits fields and options that `skills/cheese/references/handoff-gate.md:56-75,195-211` requires. |
| `build -> melt`: command references | ok | `scripts/render_generated_regions.py:269-299,319` reads the static manifest. `uv run python scripts/render_generated_regions.py --check` passed. |
| `build -> melt`: bundle packaging | ok | `scripts/build_pyz.py:25-43,541-586` discovers command modules. The committed bundle accepted `--help` and dispatched `conflict-summary --help`. |

## STE100 status

compliant

## Follow-ups

- Update the shared handoff gate contract for an incomplete Git operation. Define when the standard tail becomes safe.
