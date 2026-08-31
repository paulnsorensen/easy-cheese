# Writer-output corpus

Each `*.json` file here is one writer view plus the host invocation it was
produced against, replayed by `scripts/contract_benchmarks.py` through
`normalize_agent_output`. The weekly `contract-benchmarks` workflow publishes
the resulting report; `tests/python/test_contract_benchmark_corpus.py` replays
the same corpus on every pull request as a backward-compat canary.

## Case format

```json
{
  "name": "review-result-clean",
  "provenance": "captured",
  "source": "where this payload came from, sanitized",
  "expect_first_pass_valid": true,
  "writer_view": {"kind": "...", "payload": {}},
  "invocation": {},
  "repair_view": {}
}
```

- `name` — unique across the corpus; the report and the canary key on it.
- `provenance` — `captured` for real agent output, `synthetic` for a payload
  authored by hand. The <10% first-pass-invalid budget is measured over
  captured cases only.
- `source` — free text recording the origin (skill, run, date), sanitized of
  anything private.
- `expect_first_pass_valid` — the validity recorded when the case landed. A
  replay that disagrees fails CI: a contract change flipped a stored payload.
- `writer_view` / `invocation` — plain JSON, exactly as the boundary sees them.
- `repair_view` — optional second attempt, replayed only after an invalid first
  pass; rejected on a case recorded as valid, where it can never run.

## Adding cases

Sanitize first: strip paths, identifiers, and prose that should not be public.
Drop the file in, run `python3 scripts/contract_benchmarks.py`, and record the
validity it reports as `expect_first_pass_valid`.

The corpus ships with four synthetic seeds derived from the representative
benchmark in `docs/architecture/milknado-semantic-boundary-reassessment.md`.
Until captured cases land, the budget reports as not measurable — see
[issue #406](https://github.com/paulnsorensen/easy-cheese/issues/406).
