# ADR: Preserve artifact schema-validator injection until a major release

Decision status: accepted

## Context

`easy-cheese-schemas` 1.1 published `resolve_artifact(..., schema_validator=...)` and a positional validator argument on `resolve_verified_bytes`. Removing either callable seam under a refactor release breaks existing callers with `TypeError`, even though the built-in registry is the only production validator inside this repository.[^1]

The package's post-1.0 policy requires backward-compatible public signatures within the same major version.[^2]

## Decision

Keep `SchemaValidator = Callable[[bytes, str], None]` and accept the validator on both artifact-resolution entry points. The default remains `_validate_registered_schema`; a supplied validator runs after integrity and JSON-shape checks and before verified bytes are materialized.[^3]

Do not export `SchemaValidator` through `artifacts.__all__`, because the published surface defined the alias without adding it to wildcard exports.[^4]

## Alternatives

- Remove the seam because repository production callers use only the default: rejected until a major release; local YAGNI does not override a published compatibility contract.
- Bump immediately to 2.0: rejected for the contained artifact-abstraction refactor that introduced this decision.

## Consequences

Internal code does not need to inject the default validator. The compatibility seam remains covered at both public entry points and may be removed only with an explicit major-version change.[^5]

[^1]: https://github.com/paulnsorensen/easy-cheese/pull/574
[^2]: docs/easy-cheese-schemas.md:149-159
[^3]: src/easy_cheese_schemas/artifacts.py:58-114,525-554
[^4]: src/easy_cheese_schemas/artifacts.py:23-34
[^5]: tests/schemas/python/test_artifact_resolution.py:498-548
