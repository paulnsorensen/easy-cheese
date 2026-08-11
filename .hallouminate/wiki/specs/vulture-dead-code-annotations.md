# Centralized semantic Vulture adapter

Status: approved 2026-08-10
Source: promoted from the Mold artifact at `$XDG_DATA_HOME/cheese/paulnsorensen-easy-cheese/specs/vulture-dead-code-annotations.md`
Typed plan: `vulture-dead-code-annotations-plan`, revision 1, digest `sha256:77861408e55d7016b0225790c33fef31bb66f050483bcb694176a6addca722aa`

`just lint-py-dead-code` should keep Vulture's broad dead-code signal while moving inferable dynamic-use policy out of 95 source-local suppressions and into one owner-qualified adapter. LSP remains a design and review oracle; the production check depends only on the standard library and pinned Vulture 2.16.

## Problem

`just lint-py-dead-code` currently preserves Vulture's default-confidence dead-code signal, but 103 bare `# noqa` annotations across 16 files encode dynamic-use policy in source. Ninety-five are inferable from stable ownership or callback semantics; leaving them local makes the policy cross-cutting and difficult to review.

## Goals

- Keep Vulture as the detector and fail every unclassified finding.
- Replace 95 inferable source annotations with one owner-qualified semantic classifier.
- Preserve the current default confidence range, attrs validator handling, report ordering, and process outcomes.
- Keep LSP as a design and review oracle rather than a runtime dependency.

## Non-goals

- Do not reintroduce a generated or checked-in symbol whitelist.
- Do not generalize acceptance to every attrs field, Enum member, NamedTuple field, exported field, or override in the repository.
- Do not remove the eight context-specific `# noqa` annotations outside the accepted owner-qualified categories.
- Do not add Pyright or another LSP server to the lint runtime.

## Approach

Fork coverage:

- Preserve whitelist-free Vulture behavior and fail every unclassified finding.
- Use LSP as a design and review oracle, not as a production lint dependency.
- Use Vulture 2.16 through its documented Python scanner API behind a private immutable finding boundary.
- Accept only owner-qualified schema and exact callback categories, remove 95 annotations, and retain eight context-specific annotations.

Add `scripts/check_dead_code.py` as the single dead-code policy boundary. `just lint-py-dead-code` runs it with Vulture 2.16 supplied explicitly by `uvx --from vulture==2.16`. The script uses the documented `vulture.Vulture` scanner API, immediately converts returned items into an immutable private finding value, indexes source ownership with the standard-library AST, filters only accepted dynamic-use categories, prints unclassified findings in Vulture order, and exits with the corresponding Vulture-compatible status.

Accepted categories are deliberately owner-qualified:

1. attrs fields owned by classes under `src/easy_cheese_schemas`;
2. Enum members owned by classes under `src/easy_cheese_schemas`;
3. exact callback methods whose imported base identity and method name match the policy: `urllib.request.HTTPRedirectHandler.redirect_request`, `html.parser.HTMLParser.handle_starttag`, `handle_data`, `handle_endtag`, and `urllib.request.HTTPSHandler.https_open`;
4. functions decorated with `pytest.fixture(autouse=True)`;
5. existing attrs validator decorators through Vulture's `ignore_decorators=["@*.validator"]` scanner option.

Local bare `# noqa` remains valid for opaque dynamic contracts outside these categories. A similar-looking construct with the wrong owner package, base identity, method name, or decorator arguments remains unclassified and fails.

## Decisions

- LSP is a design oracle, not a production dependency.
- Vulture's pinned programmatic Python API is the integration seam; CLI report parsing is rejected because Vulture 2.16 exposes no machine-readable output.
- Semantic acceptance is owner-qualified and removes 95 annotations; eight context-specific annotations stay local.
- Vulture remains whitelist-free: the adapter contains category rules, not exact symbol names.

## Interface sketches

```python
@dataclass(frozen=True, slots=True)
class _Finding:
    path: Path
    first_line: int
    last_line: int
    name: str
    kind: str
    confidence: int
    report: str

@dataclass(frozen=True, slots=True)
class _ScanResult:
    status: int
    findings: tuple[_Finding, ...]

def _scan(paths: Sequence[str]) -> _ScanResult: ...
def _accepted_reason(finding: _Finding, sources: Mapping[Path, ast.Module]) -> str | None: ...
def main(argv: Sequence[str] | None = None) -> int: ...
```

The only cross-module interface is the command invoked by `just lint-py-dead-code`; all classifier structures remain private to the script.

## Acceptance

- **AC-1:** `just lint-py-dead-code` succeeds on the repository after exactly the 95 owner-qualified annotations are removed; the eight context-specific annotations remain.
- **AC-2:** Each accepted attrs, Enum, exact callback, and autouse-fixture fixture produces no reported finding.
- **AC-3:** Similar-looking near-misses and an ordinary unannotated dead function are printed in deterministic Vulture order and cause exit status 3.
- **AC-4:** Invalid or unreadable input preserves Vulture's non-success input status and diagnostic instead of being converted into a clean result.
- **AC-5:** The recipe supplies Vulture 2.16 explicitly, existing validator-decorator behavior is preserved, and every affected committed `.pyz` bundle is regenerated and passes the bundle check.
- **AC-6:** An unclassified 60%-confidence finding is still reported with exit status 3, proving the adapter preserves Vulture's default confidence floor.
- **AC-7:** The production command needs only the standard library plus pinned Vulture and starts no LSP process; it succeeds when LSP imports and child-process creation are forbidden.

## Test contracts

| Acceptance | interface | seam | deterministic expected failure | mode | interface version | matrix rows |
| --- | --- | --- | --- | --- | --- | --- |
| AC-1 | `just lint-py-dead-code` | repository dead-code command | pre-change command still requires the inferable local suppressions | tracer |  |  |
| AC-2 | dead-code policy classifier | AST owner/category decision | pre-change code has no centralized classifier for accepted fixtures | tracer |  |  |
| AC-3 | dead-code command output and exit status | unclassified Vulture findings | pre-change code cannot distinguish accepted categories from near-misses without source annotations | tracer |  |  |
| AC-4 | dead-code command input handling | Vulture scan status boundary | an adapter that drops scanner input failure returns the wrong status or diagnostic | tracer |  |  |
| AC-5 | `just lint-py-dead-code` and bundle verification | pinned scanner invocation plus regenerated bundles | the current recipe is unpinned and regenerated bundles do not yet contain the annotation cleanup | tracer |  |  |
| AC-6 | dead-code command output and exit status | Vulture default-confidence boundary | an adapter that raises the confidence floor silently drops a 60%-confidence dead function | tracer |  |  |
| AC-7 | dead-code command under dependency/process guards | in-process Vulture scanner boundary | an adapter that imports an LSP client or starts a language-server process fails under the guard | tracer |  |  |

## Grill

- **Version drift:** pin 2.16 and isolate every Vulture object access in `_scan`; the rest of the module consumes `_Finding` only.
- **Classifier overreach:** exact owner package, resolved import identity, method name, and decorator arguments are mandatory; every accepted category gets an adjacent near-miss fixture that must fail.
- **Mixed scans:** accepted findings disappear, unclassified findings retain Vulture ordering and reports, and any unclassified finding returns status 3.
- **Input failures:** scanner input errors outrank semantic filtering and preserve their original non-success status.
- **Opaque contracts:** the eight context-specific annotations stay local rather than growing generic rules.
- **LSP variability:** no LSP process, configuration, or output participates in the command.

## Open questions

None. The LSP role, Vulture integration seam, semantic categories, retained local annotations, and failure behavior are settled.

## Quality gates

- `python3 -m pytest tests/python/test_check_dead_code.py -q`
- `just lint-py-dead-code`
- `just bundle`
- `python3 scripts/check_bundles.py`

## Gate applicability

```yaml
gate_applicability:
  disposition: red-required
  work_class: behavior
  ui_surface: non-browser
```

## Curds

Host validation produced CurdPlan `vulture-dead-code-annotations-plan`, revision 1, digest `sha256:77861408e55d7016b0225790c33fef31bb66f050483bcb694176a6addca722aa`.

| Order | Curd | Owned scope | Depends on | Observable outcome |
| --- | --- | --- | --- | --- |
| 1 | `vulture-dead-code-annotations-semantic-adapter` | `scripts/check_dead_code.py`; `justfile`; `tests/python/test_check_dead_code.py` | — | The pinned private adapter powers the recipe, accepted and near-miss fixtures prove every semantic boundary, unclassified findings preserve Vulture reports/status, and no LSP runtime is used. |
| 2 | `vulture-dead-code-annotations-annotation-migration` | `conftest.py`; `src/**/*.py`; `shared/**/*.py`; `scripts/**/*.py`; `.github/scripts/**/*.py`; `tests/**/*.py`; `**/*.pyz` | `vulture-dead-code-annotations-semantic-adapter` | Exactly 95 inferable annotations are removed, eight opaque annotations remain, the repository check passes, and every affected committed bundle is rebuilt and verified. |

The canonical `PlannerResult` and `CurdPlan` sidecars are persisted with the Mold artifact as `vulture-dead-code-annotations-planner-result.json` and `vulture-dead-code-annotations-curd-plan.json`.
