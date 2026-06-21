# TypeDB Local Initialization

The local Docker Compose stack runs TypeDB Community Edition for development.

Schema loading is handled by the Axis API/ontology tooling rather than by a
container entrypoint script. This keeps schema changes versioned with the API
service and avoids hidden initialization behavior.

The development image is pinned by digest so local schema behavior is
reproducible across machines. Production deployment manifests should keep the
same rule: no floating database image tags.
