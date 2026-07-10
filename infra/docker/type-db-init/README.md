# TypeDB Local Initialization

The local Docker Compose stack runs TypeDB Community Edition for development.

Schema loading is handled by the Axis API/ontology tooling rather than by a
container entrypoint script. This keeps schema changes versioned with the API
service and avoids hidden initialization behavior. Load (or re-load) the axis_
meta-ontology schema once per environment before enabling ontology mutations:

```
cd services/api
uv run python -m axis_api.ontology.bootstrap
```

The command reads `AXIS_TYPEDB_*`, creates the database if absent, and defines
the schema in `src/axis_api/ontology/schema.tql`. It is idempotent to re-run.
Connector promotions only write to TypeDB when `AXIS_ONTOLOGY_MUTATIONS_ENABLED`
is set; each write is verified with a read-back before a proposal is marked
`promoted_to_graph`.

The development image is pinned by digest so local schema behavior is
reproducible across machines. Production deployment manifests should keep the
same rule: no floating database image tags.
