# TypeDB Local Initialization

The local Docker Compose stack runs TypeDB Community Edition for development.

Schema loading is handled by the Axis API/ontology tooling rather than by a
container entrypoint script. This keeps schema changes versioned with the API
service and avoids hidden initialization behavior.

The development image uses the TypeDB 3.x line because the Python driver resolved
by `uv` is a 3.x driver. Production deployment manifests should pin exact image
versions after the first supported release train is selected.
