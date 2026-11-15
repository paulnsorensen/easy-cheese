---
status: reviewed
last_verified: 2026-09-06
confidence: high
sources:
  - src/easy_cheese_schemas/_schema_catalog.py
  - scripts/build_schema_site.py
  - .github/workflows/schemas-site.yml
  - tests/schemas/python/goldens/
---

# Schema root domain and catalog site

`SCHEMA_ROOT = "https://schemas.easy-cheese.dev"`
(`src/easy_cheese_schemas/_schema_catalog.py`) namespaces the registered
contract schema URIs shipped in the `easy-cheese-schemas` PyPI package. The
URIs are resolved in-process by `schema_runtime.schema_bytes()`; nothing in the
package fetches them over the network. The domain is owned (registered
2026-08-16, GoDaddy, expires 2028-08-16), so the URIs are now real,
dereferenceable URLs.

## What serves the catalog

The site is a **Cloudflare Pages** project named `easy-cheese-schemas`
(Direct Upload, not Git-connected). `scripts/build_schema_site.py` renders the
deployable tree from the catalog itself:

- one extensionless file per registered URI (`/curd-plan`, `/review-request`,
  …), holding exactly `schema_bytes(uri)`;
- `_headers`, which sets `Content-Type: application/schema+json; charset=utf-8`
  plus open CORS on every path;
- `index.html`, listing the catalog and the package version.

The bytes are never hand-maintained. They equal the goldens in
`tests/schemas/python/goldens/*.json`. Adding a contract to the catalog adds a
served path on the next deploy.

## Deploy pipeline

`.github/workflows/schemas-site.yml` runs on pushes to `main` that touch
`src/easy_cheese_schemas/**` (or the script/workflow), and on
`workflow_dispatch`. The job:

1. verifies the generated tree against the goldens (`test_schema_site.py`) — a
   red run here means the deploy would serve drifted bytes;
2. builds the tree;
3. ensures the Pages project exists (idempotent);
4. deploys with `wrangler pages deploy` via `cloudflare/wrangler-action`.

The deploy step is gated on the `CLOUDFLARE_ACCOUNT_ID` repository variable, so
the workflow is inert (build + verify only) until Cloudflare is wired.

### Required GitHub configuration

- Repository **variable** `CLOUDFLARE_ACCOUNT_ID`.
- Repository **secret** `CLOUDFLARE_API_TOKEN`.

## Gotchas (learned during first deploy, 2026-09-06)

These three points each cost a failed run. Keep them recorded.

1. **Token scope, not membership.** The API token must carry
   **Account → Cloudflare Pages → Edit**. A user's account role ("Super
   Administrator – All Privileges") does **not** grant a token anything —
   token permissions are a separate, explicit grant. A broad-looking token
   without the Pages permission fails with `Authentication error [code: 10000]`
   on `/pages/projects/easy-cheese-schemas`. If the "Cloudflare Pages"
   permission group is missing from the token editor, open **Workers & Pages**
   in the dashboard once to provision the product, then it appears.

2. **`packageManager: npm` is required on `wrangler-action`.** The action infers
   the package manager from a lockfile. The repo's root `pnpm-lock.yaml` (the
   Starlight docs) makes it pick pnpm, but this Python-only job never installs
   Node/pnpm, so the wrangler install fails with
   `Unable to locate executable file: pnpm`. Pin `packageManager: npm`.

3. **The Pages project must pre-exist.** Current wrangler (4.129.x) no longer
   auto-creates a Pages project on first `pages deploy` — it errors
   `The Pages project "easy-cheese-schemas" does not exist`. The workflow
   creates it idempotently (`pages project list` guard, then
   `pages project create ... --production-branch=main`). The dashboard "create
   project" flow now steers new static sites to Git-connected **Workers Static
   Assets**, which is a different, conflicting pipeline — avoid it; let the
   workflow own creation.

## Custom domain

`schemas.easy-cheese.dev` is attached to the Pages project as a custom domain.
`.dev` is HSTS-preloaded (HTTPS only); Cloudflare provisions the certificate.
The apex `easy-cheese.dev` is separate and not required for the catalog.

## Registrar

Keep **auto-renew** on at GoDaddy. The root is baked into published PyPI
releases; a lapse hands the namespace to drop-catchers. Keep the privacy proxy.

## Acceptance (verified live 2026-09-06)

```
curl https://schemas.easy-cheese.dev/curd-plan
```

returns bytes identical to `tests/schemas/python/goldens/curd-plan.json` with
`content-type: application/schema+json; charset=utf-8` and
`access-control-allow-origin: *`.
