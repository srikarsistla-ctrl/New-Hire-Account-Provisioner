# Cloudflare Workers deployment

This deployment keeps FastAPI, Python, LangChain, and the existing frontend.
The original local server remains available with `pip install -r requirements-local.txt`
and `uvicorn app.main:app --reload`.

Validation: 78 automated tests pass. The deployment dry run passes, and
`scripts/check-cloudflare.py` passes against Wrangler's local Workers runtime and
local D1, including page/assets routing and the four official provisioning cases.
Live AI and remote deployment still require verification after deployment.

## Storage and behavior

The Worker uses D1 through its binding API, not a local SQLite file. For this small
shared sandbox it stores one JSON document containing mock accounts, provider
settings, requests, and audit logs. Every write conditionally updates the saved
version. A conflicting write returns HTTP 409 without saving any partial actions;
reload and retry. No real SaaS account side effects occur.

The document is limited to 900,000 bytes. At the limit new writes return HTTP 507;
existing records remain readable. This is a bounded hackathon demo, not a scalable
production database design. Export records before an owner archives/resets the
database. The local SQLAlchemy implementation and Worker implementation have
separate storage and do not synchronize. Both expose the same frontend API.

## One-time setup

1. In Cloudflare, create a D1 database named `new-hire-provisioner`.
2. Put its Database ID in `wrangler.jsonc` under `d1_databases[0].database_id`.
   This ID is configuration, not a secret. Commit the updated file.
3. Open the D1 Console and run the SQL from `migrations/0001_sandbox.sql`, or use:
   `uv run pywrangler d1 migrations apply new-hire-provisioner --remote`.
4. Create a Worker from this GitHub repository. Use the Worker name
   `new-hire-account-provisioner`, branch `main`, and repository root directory.
5. Use a build environment with `uv >= 0.13.4`. Set the build command to
   `python -m pip install 'uv>=0.13.4' && uv sync --locked && node scripts/build-cloudflare.mjs`.
   Set the deploy command to `uv run pywrangler deploy`.
   Disable preview builds initially. Do not use `wrangler deploy --assets frontend`.
6. Add runtime secret `GROQ_API_KEY` to the Worker. Add runtime variables
   `GROQ_MODEL=llama-3.3-70b-versatile` and `ACCESS_POLICY_MODE=approval`.
   Build-only environment secrets are not sufficient: verify the key appears in
   the deployed Worker's runtime Settings > Variables and Secrets.
7. Deploy, then verify `/api/health`, `/api/catalog`, the homepage, `/approval`,
   and `/dashboard`. Generate a recommendation and confirm it reports AI mode
   before recording the AI demo. Missing/invalid keys produce a labeled fallback.

For CLI deployment, install current uv and Node, run `uv sync --locked`, then
`uv run pywrangler login`, apply the migration, run
`uv run pywrangler secret put GROQ_API_KEY`, and `uv run pywrangler deploy`.
Never commit `.env`, `.dev.vars`, or keys into configuration or frontend assets.

## Local Worker checks

`uv run pywrangler d1 migrations apply new-hire-provisioner --local`

`uv run pywrangler dev`

With that server running and AI keys disabled, use the local test environment to
run `python scripts/check-cloudflare.py`. It only contacts localhost and writes
fictional records to the local D1 database.

Use a separate environment from the local Python 3.12 server when necessary:
set `UV_PROJECT_ENVIRONMENT=.venv-workers`. Pywrangler supplies the Workers
runtime and resolves Python packages for WebAssembly. The compatibility date is
pinned to Python 3.13; `pylock.toml` locks its WebAssembly dependencies. The build
creates HTML, JS, and CSS in ignored `public/`, preserving `/static/` paths, and
copies only the required Python source into ignored `worker-src/`. This prevents
local environments, tests, and unrelated source from entering the Worker bundle.

Run the original tests plus Worker API/storage tests using the local environment:
`python -m pytest -q`. These verify contracts and conditional SQL writes using
SQLite as a D1 test substitute. A deployed Worker and real provider key are still
required to verify live Cloudflare and AI behavior.
