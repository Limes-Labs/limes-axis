"""Load the axis_ meta-ontology schema into TypeDB.

Enabling ``AXIS_ONTOLOGY_MUTATIONS_ENABLED`` makes connector promotions write
real entities into TypeDB. Those writes target the ``axis_asset`` type defined in
``schema.tql``; the database and schema must therefore exist before the first
promotion. ``OntologyClient.ensure_database`` creates an empty database but does
NOT define the schema, so operators run this bootstrap once per environment:

    python -m axis_api.ontology.bootstrap

It is idempotent to re-run: TypeDB ``define`` stages are additive and re-defining
an already-defined type is a no-op.
"""

from __future__ import annotations

from pathlib import Path

from axis_api.config import Settings
from axis_api.ontology.client import OntologyClient, OntologyClientConfig

SCHEMA_PATH = Path(__file__).with_name("schema.tql")


def read_meta_ontology_schema() -> str:
    return SCHEMA_PATH.read_text(encoding="utf-8")


def _client_from_settings(settings: Settings) -> OntologyClient:
    return OntologyClient(
        OntologyClientConfig(
            address=settings.typedb_address,
            username=settings.typedb_username,
            password=settings.typedb_password,
            database=settings.typedb_database,
        )
    )


def load_meta_ontology_schema(settings: Settings | None = None) -> str:
    """Create the ontology database (if needed) and define the meta-ontology.

    Returns the database name that was bootstrapped.
    """
    resolved = settings or Settings()
    client = _client_from_settings(resolved)
    try:
        client.ensure_database()
        client.load_schema(read_meta_ontology_schema())
    finally:
        client.close()
    return resolved.typedb_database


def main() -> None:  # pragma: no cover - thin CLI wrapper
    database = load_meta_ontology_schema()
    print(f"Loaded axis meta-ontology schema into TypeDB database '{database}'.")


if __name__ == "__main__":  # pragma: no cover
    main()
