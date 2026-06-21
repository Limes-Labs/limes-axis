from dataclasses import dataclass


@dataclass(frozen=True)
class OntologyClientConfig:
    address: str
    username: str
    password: str
    database: str = "axis"
    tls_enabled: bool = False


class OntologyClient:
    """Thin TypeDB boundary.

    The rest of Axis should depend on this boundary instead of importing the
    TypeDB driver directly. The driver import is intentionally lazy so unit tests
    for schema files do not need a running TypeDB server.
    """

    def __init__(self, config: OntologyClientConfig) -> None:
        self.config = config
        self._driver = None

    def connect(self) -> None:
        from typedb.driver import Credentials, DriverOptions, DriverTlsConfig, TypeDB

        tls_config = (
            DriverTlsConfig.enabled_with_native_root_ca()
            if self.config.tls_enabled
            else DriverTlsConfig.disabled()
        )
        self._driver = TypeDB.driver(
            self.config.address,
            Credentials(self.config.username, self.config.password),
            DriverOptions(tls_config),
        )

    def ensure_database(self) -> None:
        if self._driver is None:
            self.connect()
        if not self._driver.databases.contains(self.config.database):
            self._driver.databases.create(self.config.database)

    def load_schema(self, schema_text: str) -> None:
        if not schema_text.strip():
            raise ValueError("TypeDB schema cannot be empty.")
        from typedb.driver import TransactionType

        self.ensure_database()
        transaction = self._driver.transaction(self.config.database, TransactionType.SCHEMA)
        try:
            transaction.query(schema_text).resolve()
            transaction.commit()
        except Exception:
            if transaction.is_open():
                transaction.rollback()
            raise

    def close(self) -> None:
        if self._driver is not None:
            self._driver.close()
            self._driver = None
