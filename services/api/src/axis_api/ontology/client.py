from collections.abc import Iterable, Mapping
from dataclasses import dataclass

OntologyQueryRow = dict[str, object] | str


@dataclass(frozen=True)
class OntologyClientConfig:
    address: str
    username: str
    password: str
    database: str = "axis"
    tls_enabled: bool = False
    request_timeout_millis: int | None = None


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
        options = (
            DriverOptions(tls_config)
            if self.config.request_timeout_millis is None
            else DriverOptions(
                tls_config,
                request_timeout_millis=self.config.request_timeout_millis,
            )
        )
        self._driver = TypeDB.driver(
            self.config.address,
            Credentials(self.config.username, self.config.password),
            options,
        )

    def database_exists(self) -> bool:
        """Return database reachability without creating or mutating state."""

        if self._driver is None:
            self.connect()
        return bool(self._driver.databases.contains(self.config.database))

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

    def execute_write(self, query_text: str) -> None:
        if not query_text.strip():
            raise ValueError("TypeDB write query cannot be empty.")
        from typedb.driver import TransactionType

        self.ensure_database()
        transaction = self._driver.transaction(self.config.database, TransactionType.WRITE)
        try:
            transaction.query(query_text).resolve()
            transaction.commit()
        except Exception:
            if transaction.is_open():
                transaction.rollback()
            raise

    def execute_read(self, query_text: str) -> list[OntologyQueryRow]:
        if not query_text.strip():
            raise ValueError("TypeDB read query cannot be empty.")
        from typedb.driver import TransactionType

        self.ensure_database()
        transaction = self._driver.transaction(self.config.database, TransactionType.READ)
        try:
            return normalize_query_answer(transaction.query(query_text).resolve())
        finally:
            if transaction.is_open():
                transaction.close()

    def schema(self) -> str:
        self.ensure_database()
        return self._driver.databases.get(self.config.database).schema()

    def drop_database(self) -> None:
        if self._driver is None:
            self.connect()
        if self._driver.databases.contains(self.config.database):
            self._driver.databases.get(self.config.database).delete()

    def close(self) -> None:
        if self._driver is not None:
            self._driver.close()
            self._driver = None


def normalize_query_answer(answer: object) -> list[OntologyQueryRow]:
    if _method_returns_true(answer, "is_concept_documents"):
        return [
            _mapping_to_public_dict(document)
            for document in answer.as_concept_documents()
            if isinstance(document, Mapping)
        ]

    if _method_returns_true(answer, "is_concept_rows"):
        return [_concept_row_to_mapping(row) for row in answer.as_concept_rows()]

    if isinstance(answer, Mapping):
        return [_mapping_to_public_dict(answer)]

    if isinstance(answer, str):
        return [answer]

    if isinstance(answer, Iterable):
        rows: list[OntologyQueryRow] = []
        for item in answer:
            if isinstance(item, Mapping):
                rows.append(_mapping_to_public_dict(item))
            elif _looks_like_concept_row(item):
                rows.append(_concept_row_to_mapping(item))
            else:
                rows.append(str(item))
        return rows

    return [str(answer)]


def _method_returns_true(value: object, method_name: str) -> bool:
    method = getattr(value, method_name, None)
    if not callable(method):
        return False
    return bool(method())


def _mapping_to_public_dict(mapping: Mapping[object, object]) -> dict[str, object]:
    return {str(key): _public_value(value) for key, value in mapping.items()}


def _looks_like_concept_row(value: object) -> bool:
    return callable(getattr(value, "column_names", None)) and callable(
        getattr(value, "get", None)
    )


def _concept_row_to_mapping(row: object) -> dict[str, object]:
    return {
        str(column_name): _public_value(row.get(column_name))
        for column_name in row.column_names()
    }


def _public_value(value: object) -> object:
    if isinstance(value, Mapping):
        return _mapping_to_public_dict(value)
    if isinstance(value, list):
        return [_public_value(item) for item in value]
    if isinstance(value, tuple):
        return [_public_value(item) for item in value]
    if _method_returns_true(value, "is_value"):
        return value.as_value().get()
    if _method_returns_true(value, "is_attribute"):
        return value.as_attribute().get_value()
    if _method_returns_true(value, "is_entity") or _method_returns_true(
        value, "is_relation"
    ):
        return _instance_identity(value)
    if _method_returns_true(value, "is_type"):
        return _type_label(value)
    return value


def _instance_identity(value: object) -> dict[str, object]:
    identity: dict[str, object] = {}
    get_iid = getattr(value, "get_iid", None)
    if callable(get_iid):
        identity["iid"] = get_iid()
    get_type = getattr(value, "get_type", None)
    if callable(get_type):
        identity["type"] = _type_label(get_type())
    return identity or {"repr": str(value)}


def _type_label(value: object) -> object:
    get_label = getattr(value, "get_label", None)
    if callable(get_label):
        return get_label()
    return str(value)
