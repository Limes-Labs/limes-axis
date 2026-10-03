# Optional public institutional context acceptance

This is an isolated reviewable consumer integration, not product deployment.
The default API and its committed locks do not depend on GovCore. After normal
`uv sync --locked` in `services/api`, explicitly install the reviewed MIT wheel:

```sh
uv pip install --python services/api/.venv/bin/python --no-deps tools/govcore/govcore_client-0.1.0-py3-none-any.whl
services/api/.venv/bin/python -m pytest services/api/tests/test_public_institutional_context.py -q
services/api/.venv/bin/python tools/govcore/prove_loopback.py
```

The optional route is registered only by `create_app(public_context=PublicContextConfig(...))`.
The operator must supply a fixed approved origin and local allowed tenants, explicitly
set `enabled=True`, and grant `institutional:context:read` through Axis identity policy.
No environment file, connector registration, tenant migration, ontology write or action
execution is required. A normal frozen sync may remove this optional wheel; reinstall it
explicitly for the acceptance lane. The default API continues to import without the SDK.

See [the proposed boundary ADR](../../docs/adr/0019-public-institutional-context.md).
The wheel is independently authored public GovCore SDK code, with its MIT license inside
the archive and `LICENSE` beside it. It contains no GovCore service implementation,
product source, pilot data, credentials or private records. `sdk-manifest.json` records
its hash and source provenance. The loopback script creates only a disposable in-memory
synthetic host tenant; it neither migrates nor connects to an Axis tenant database.
