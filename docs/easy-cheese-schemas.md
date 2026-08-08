# easy-cheese-schemas

The machine-readable artifact contracts of [easy-cheese](https://github.com/paulnsorensen/easy-cheese), published as an installable package: run manifests, decompositions, curd blocks, PR plans, and the readiness gate, as [attrs](https://www.attrs.org) types with [cattrs](https://catt.rs) structuring and explicit schema-version tolerance.

```sh
pip install easy-cheese-schemas
```

Requires Python 3.11 or newer. cattrs floors at 3.10; 3.11+ skips the `exceptiongroup` dependency, and 3.10 reaches end of life in October 2026.

## What this is, and what it is not

It is the artifact vocabulary: the types an external producer or consumer needs to write or read an easy-cheese document without reimplementing its field rules.

It is not the enforcement path — not yet. In v0.1 the types are **derived from** easy-cheese's existing hand-rolled validators (`src/fanout/validate_*.py`), which still run unchanged inside the repo. A conformance suite pins the two together: every fixture the validators accept must structure cleanly through these types, and every fixture they reject must fail to structure. Until the validators are migrated onto these types, treat that suite as the reason to trust them, and expect the derived-types arrangement to be retired rather than extended.

Also not published: easy-cheese's corpus and layout assumptions (`paths.py`) and the findings report grammar. Those are repo-internal and stay unversioned on purpose.

## Not enforced in v0.1

The types check field shape and the collection invariants below, but a document that satisfies them can still be rejected by `src/fanout/validate_*.py`, which enforces cross-field rules these types do not yet carry. Structuring cleanly is therefore necessary, not sufficient. Do not read a clean `Loaded` as "easy-cheese will accept this".

Enforced here: required fields and their types, enum membership, curd file-disjointness, wiring DAG acyclicity and unknown `W<n>` references, wave size and curd surface floors, and the PR-plan shape rules.

Not enforced here, and checked only by the validators:

- **`agent_resolution` consistency** — exactly one accepted attempt; the resolved agent matching that attempt; attempt and resolved power meeting the request's `minimum_power`; prompt-only permission enforcement implying `degraded` and a read-only request; an unknown resolved power implying `degraded`; a preferred-exact acceptance carrying a null `fallback_reason` (and a non-preferred one carrying a reason).
- **Phase-dependent requirements** — `phase` of `post_review_complete` or `pr_publish_complete` requiring `current_review` / `post_review`.
- **Curd lifecycle** — a curd with `status: completed` requiring `review_context`.

These are the accepted derivation gap described above, not oversights, and they are retired when the validators migrate onto these types.

## Usage

`load` structures a raw mapping into one of the artifact types. It never raises: it returns a `Loaded` carrying the value (or `None`), the payload's `provenance`, and every problem it found, in the same `where.key must be ...` format easy-cheese's validators emit.

```python
from easy_cheese_schemas import PrGroup, load

plan = {
    "schema_version": 1,
    "branch": "feat/publish",
    "title": "Publish the schemas package",
    "base": "main",
    "commits": ["9f2c1ab"],
}
strict = load(plan, PrGroup, strict=True)
print(strict.provenance, strict.problems)
print(strict.value)

# Written by a newer producer: unknown fields are ignored, the rest still parses.
newer = load(plan | {"schema_version": 2, "reviewers": ["ada"]}, PrGroup, strict=True)
print(newer.provenance, newer.value.branch)

# Lenient: gaps are reported, not raised, and the value is still usable.
lenient = load(plan | {"depends_on": None}, PrGroup, strict=False)
print(lenient.provenance, lenient.problems)
print(lenient.value)
```

```text
Provenance.CURRENT ()
PrGroup(branch='feat/publish', title='Publish the schemas package', base='main', commits=['9f2c1ab'], body=None, depends_on=[])
Provenance.FUTURE feat/publish
Provenance.CURRENT ('PrGroup.body must be present; using default', 'PrGroup.depends_on must be a list, not NoneType')
PrGroup(branch='feat/publish', title='Publish the schemas package', base='main', commits=['9f2c1ab'], body=None, depends_on=[])
```

Problems accumulate; `load` reports every one it found in a single pass rather than stopping at the first, because the callers reporting them to a human need the whole list. `problems` is a `tuple[str, ...]` — `Loaded` is frozen, and a mutable list on a frozen carrier is an invitation to edit the evidence.

Values are not type-coerced. A `str` where a `list[str]` belongs is a problem, not eight one-character paths; `"no"` where a `bool` belongs is a problem, not `True`. Reading a document is how you find out whether to trust it, so this layer reports the mismatch rather than papering over it.

One case returns a value *and* problems: a `schema_version` stamp that is not an integer is recorded as a problem and the payload is treated as `UNSTAMPED`, because an untrustworthy stamp is not a reason to discard an otherwise readable document. Callers that gate on `value is not None` should check `problems` too.

## Outer-TDD gate receipts

The gate types are phase-neutral evidence for the Cut, Cook, and Press
boundaries:

```python
from easy_cheese_schemas import (
    GateDisposition,
    GateMode,
    GateProducer,
    GateReceipt,
    load,
)

receipt = load(raw_receipt, GateReceipt, strict=True)
if receipt.value is not None and not receipt.problems:
    payload = receipt.value.to_dict()
```

The public enums are `GateDisposition` (`RED`, `NOT_APPLICABLE`), `GateMode`
(`TRACER`, `CONTRACT_MATRIX`), `RedKind` (`BEHAVIOR`, `CONTRACT`),
`GateProducer` (`CUT`, `PRESS`), and `EvidenceOrigin` (`GENERATED`,
`ADOPTED`). `TestContract` owns its own `mode`, so a RED receipt can mix tracer
and contract-matrix contracts without a receipt-level mode. A matrix contract
also carries its non-empty `interface_version` and complete unique
`matrix_rows`; each corresponding `RedCase` binds one `matrix_row`. Tracer
contracts omit those optional fields.

`BaselineCheck`, `RedCase`, and `ProtectedFile` carry executable evidence,
observed witnesses, matrix-row bindings, and project-relative protected paths.
Commands are argv lists, not shell strings; strict loading rejects primitive
coercion, absolute paths, and parent-directory escapes. Required identity,
provenance, command, and witness strings are non-empty.
`GateReceipt.phase_token_ref` and `phase_token_sha256` bind newly issued
evidence to the pre-oracle/pre-attack phase-entry token produced by
`red-gate begin`. They are an optional pair only for reading legacy receipts;
the issuance boundary requires both, verifies the token's work/project/root and
baseline identity, and stores them in every new Cut, Press, RED, or N/A receipt.

A RED `GateReceipt` requires non-empty contracts, baseline checks, cases, and
protected files. A `not-applicable` receipt is a closed shape: it has a
non-empty `not_applicable_reason` and no guards, contracts, baseline checks,
cases, or protected files. `to_dict()` returns JSON-shaped data with enum
values flattened to their strings.

## The `schema_version` contract

```python
SCHEMA_VERSION = 1   # what this package writes and fully understands
MIN_READABLE = 1     # oldest stamp still readable; widens as the schema evolves
STAMP_KEY = "schema_version"
```

The real coupling is the **data** boundary, not the code boundary. A vendored bundle is internally consistent by construction — it ships its own copy of these types — but persisted artifacts in the durable corpus outlive the upgrade that rewrote the reader, and external producers are the entire point of publishing. So every payload carries its vintage, and a reader can tell what it is holding before it acts on it.

`classify_stamp` maps the stamp to one of five outcomes:

| Provenance | Stamp condition | Meaning |
| --- | --- | --- |
| `CURRENT` | `stamp == SCHEMA_VERSION` | Written against this exact schema. |
| `PRIOR` | `MIN_READABLE <= stamp < SCHEMA_VERSION` | One or more versions behind, still readable — the N-1 tolerance. |
| `UNSTAMPED` | key absent (or present but not an `int`, which is also reported as a problem) | No stamp. Normal for a hand-authored document, foreign for a manifest. |
| `STALE` | `stamp < MIN_READABLE` | Older than this reader supports. |
| `FUTURE` | `stamp > SCHEMA_VERSION` | Written by a newer easy-cheese. |

`FUTURE` is not a rejection. Recognized fields parse, unknown fields are ignored, and the caller gets `provenance=FUTURE` so it can decide whether to act, warn, or refuse. Provenance is orthogonal to validity: a `FUTURE` payload can still be structurally invalid, and a `CURRENT` one can still collect problems.

## Two-tier strictness by artifact class

`load` does not decide strictness — `strict` is the caller's keyword argument. The tiers are a convention about which default each artifact class deserves:

- **Markdown documents** (specs, findings, handoffs) are hand-authored and hand-edited. A missing stamp is normal, so they are read **lenient**: documented defaults are filled in, every gap is recorded in `problems`, and the caller still gets a usable value.
- **JSON/YAML manifests** are machine-written. A missing stamp means the payload is foreign, so they are read **strict**: full cattrs validation, with the raised exception group flattened into `problems` and `value=None` on failure. An explicit `--lax` escape exists at the CLI boundary for the case where a human is knowingly hand-repairing a manifest.

## Stability policy

The package is semver'd, and the version governs the **artifact contracts**, not just the Python API. `SCHEMA_VERSION` and the package version move independently: a schema bump is always a major bump, but not every major bump is a schema bump.

- **Patch** — no contract change. Bug fixes, problem-message wording, documentation.
- **Minor** — additive only. New optional fields, new types, new exports. Every artifact a previous minor could write is still read as `CURRENT`, and every artifact a previous minor could read still parses.
- **Major** — a breaking contract change: a removed or renamed field, a narrowed type, a field made required, or a raised `MIN_READABLE`. Accompanied by a `SCHEMA_VERSION` bump, so previously-written artifacts become `PRIOR` or `STALE` rather than silently misparsing.

The **additive-only discipline** is what makes `FUTURE` provenance safe, and it is a hard rule, not a preference. Because unknown fields are ignored, an older reader handed a newer artifact will silently drop anything it does not recognize. That is correct behavior when new fields are additive and optional, and it is data loss when they are not — the older reader would produce a value that looks complete and is not. So within a `SCHEMA_VERSION`, new fields must be additive and optional. Anything else waits for the major bump.

Pre-1.0 caveat: while the version is `0.x`, minor bumps may break. The policy above binds from 1.0.

## Releasing (repo owner)

**A pending publisher must exist on PyPI before the first publish.** Publishing uses PyPI Trusted Publishing (OIDC), so no long-lived token is stored in the repository — but that means PyPI has to be told, in advance, which workflow in which repository is allowed to publish. Create the pending publisher on PyPI with the project name, the repository, and the publishing workflow's filename. This is a one-time manual step and it cannot be automated: without it, the first release run fails at upload.

After that, releases are automatic — a version bump to `pyproject.toml` landing on `main` triggers the publish.

## License

MIT.
