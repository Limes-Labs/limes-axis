import hashlib
import json
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from io import BytesIO
from pathlib import Path, PurePosixPath
from typing import Any, Protocol
from urllib.parse import urlparse

from pydantic import BaseModel, Field

from axis_api.config import Settings

S3_COMPATIBLE_ADAPTER = "s3_compatible"
LOCAL_FILESYSTEM_ADAPTER = "local_filesystem"
SUPPORTED_RETENTION_MODES = {"GOVERNANCE", "COMPLIANCE"}


class ObjectStoreConfigurationError(ValueError):
    pass


class StoredObjectMetadata(BaseModel):
    storage_adapter: str = Field(min_length=1)
    storage_key: str = Field(min_length=1)
    storage_uri: str = Field(min_length=1)
    content_type: str = Field(min_length=1)
    checksum_sha256: str = Field(min_length=64, max_length=64)
    size_bytes: int = Field(ge=0)


class ObjectStore(Protocol):
    adapter_name: str

    def put_json(self, key: str, payload: dict) -> StoredObjectMetadata:
        ...


class S3PutObjectClient(Protocol):
    def put_object(
        self,
        bucket_name: str,
        object_name: str,
        data: BytesIO,
        length: int,
        content_type: str,
        **kwargs: Any,
    ) -> object:
        ...


class ObjectStoreReadiness(BaseModel):
    adapter: str = Field(min_length=1)
    production_ready: bool
    bucket_configured: bool
    endpoint_configured: bool
    credentials_configured: bool
    secure_transport: bool
    object_lock_enabled: bool
    worm_retention_enabled: bool
    retention_mode: str = Field(min_length=1)
    retention_days: int = Field(ge=0)
    legal_hold_enabled: bool
    missing_requirements: list[str] = Field(default_factory=list)


class LocalObjectStore:
    adapter_name = LOCAL_FILESYSTEM_ADAPTER
    uri_scheme = "axis-local-object-store"

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)

    def put_json(self, key: str, payload: dict) -> StoredObjectMetadata:
        safe_key = self._safe_key(key)
        encoded = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        destination = self.root / safe_key
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(encoded)
        checksum = hashlib.sha256(encoded).hexdigest()
        return StoredObjectMetadata(
            storage_adapter=self.adapter_name,
            storage_key=safe_key,
            storage_uri=f"{self.uri_scheme}://{safe_key}",
            content_type="application/json",
            checksum_sha256=checksum,
            size_bytes=len(encoded),
        )

    @staticmethod
    def _safe_key(key: str) -> str:
        path = PurePosixPath(key)
        if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
            raise ValueError("Object storage keys must be relative clean paths.")
        return str(path)


class S3CompatibleObjectStore:
    adapter_name = S3_COMPATIBLE_ADAPTER

    def __init__(
        self,
        *,
        client: S3PutObjectClient,
        bucket_name: str,
        retention_mode: str,
        retention_days: int,
        legal_hold_enabled: bool,
        clock: Callable[[], datetime] | None = None,
        retention_factory: Callable[[str, datetime], object] | None = None,
    ) -> None:
        normalized_retention_mode = retention_mode.strip().upper()
        if normalized_retention_mode not in SUPPORTED_RETENTION_MODES:
            raise ObjectStoreConfigurationError(
                "S3-compatible object storage retention mode must be GOVERNANCE or COMPLIANCE."
            )
        if retention_days <= 0:
            raise ObjectStoreConfigurationError(
                "S3-compatible object storage retention days must be greater than zero."
            )

        self.client = client
        self.bucket_name = bucket_name
        self.retention_mode = normalized_retention_mode
        self.retention_days = retention_days
        self.legal_hold_enabled = legal_hold_enabled
        self.clock = clock or (lambda: datetime.now(UTC))
        self.retention_factory = retention_factory or _minio_retention

    def put_json(self, key: str, payload: dict) -> StoredObjectMetadata:
        safe_key = LocalObjectStore._safe_key(key)
        encoded = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        retain_until = self.clock() + timedelta(days=self.retention_days)
        retention = self.retention_factory(self.retention_mode, retain_until)
        self.client.put_object(
            self.bucket_name,
            safe_key,
            BytesIO(encoded),
            len(encoded),
            "application/json",
            retention=retention,
            legal_hold=self.legal_hold_enabled,
        )
        checksum = hashlib.sha256(encoded).hexdigest()
        return StoredObjectMetadata(
            storage_adapter=self.adapter_name,
            storage_key=safe_key,
            storage_uri=f"s3://{self.bucket_name}/{safe_key}",
            content_type="application/json",
            checksum_sha256=checksum,
            size_bytes=len(encoded),
        )


def _minio_retention(mode: str, retain_until: datetime) -> object:
    from minio.commonconfig import COMPLIANCE, GOVERNANCE
    from minio.retention import Retention

    minio_mode = GOVERNANCE if mode == "GOVERNANCE" else COMPLIANCE
    return Retention(minio_mode, retain_until)


def _normalize_s3_endpoint(raw_endpoint: str, secure_transport: bool) -> tuple[str, bool]:
    endpoint = raw_endpoint.strip()
    if not endpoint:
        raise ObjectStoreConfigurationError("S3-compatible object storage endpoint is required.")

    parsed = urlparse(endpoint)
    if parsed.scheme in {"http", "https"}:
        if not parsed.netloc or parsed.path not in {"", "/"}:
            raise ObjectStoreConfigurationError(
                "S3-compatible object storage endpoint must not include a path."
            )
        return parsed.netloc, parsed.scheme == "https"
    if "://" in endpoint:
        raise ObjectStoreConfigurationError(
            "S3-compatible object storage endpoint must use http or https when a scheme is set."
        )
    return endpoint, secure_transport


def _s3_client_factory(**kwargs: Any) -> S3PutObjectClient:
    from minio import Minio

    return Minio(**kwargs)


def build_object_store_readiness(settings: Settings) -> ObjectStoreReadiness:
    adapter = settings.connector_export_object_store_adapter.strip().casefold()
    retention_mode = settings.connector_export_s3_retention_mode.strip().upper()
    bucket_configured = bool(settings.connector_export_s3_bucket)
    endpoint_configured = bool(settings.connector_export_s3_endpoint)
    effective_secure_transport = settings.connector_export_s3_secure_transport
    if settings.connector_export_s3_endpoint:
        try:
            _, effective_secure_transport = _normalize_s3_endpoint(
                settings.connector_export_s3_endpoint,
                settings.connector_export_s3_secure_transport,
            )
        except ObjectStoreConfigurationError:
            endpoint_configured = False
            effective_secure_transport = False
    access_key_configured = bool(settings.connector_export_s3_access_key)
    secret_key_configured = bool(settings.connector_export_s3_secret_key)
    credentials_configured = access_key_configured and secret_key_configured
    retention_mode_supported = retention_mode in SUPPORTED_RETENTION_MODES
    retention_days_configured = settings.connector_export_s3_retention_days > 0
    object_lock_enabled = settings.connector_export_s3_object_lock_enabled
    worm_retention_enabled = (
        object_lock_enabled and retention_mode_supported and retention_days_configured
    )

    missing_requirements: list[str] = []
    if adapter != S3_COMPATIBLE_ADAPTER:
        missing_requirements.append("S3-compatible adapter")
    if not endpoint_configured:
        missing_requirements.append("endpoint")
    if not bucket_configured:
        missing_requirements.append("bucket")
    if not access_key_configured:
        missing_requirements.append("access key")
    if not secret_key_configured:
        missing_requirements.append("secret key")
    if not effective_secure_transport:
        missing_requirements.append("TLS transport")
    if not object_lock_enabled:
        missing_requirements.append("object lock")
    if not retention_mode_supported:
        missing_requirements.append("retention mode")
    if not retention_days_configured:
        missing_requirements.append("retention days")

    return ObjectStoreReadiness(
        adapter=adapter,
        production_ready=not missing_requirements,
        bucket_configured=bucket_configured,
        endpoint_configured=endpoint_configured,
        credentials_configured=credentials_configured,
        secure_transport=effective_secure_transport,
        object_lock_enabled=object_lock_enabled,
        worm_retention_enabled=worm_retention_enabled,
        retention_mode=retention_mode,
        retention_days=max(settings.connector_export_s3_retention_days, 0),
        legal_hold_enabled=settings.connector_export_s3_legal_hold_enabled,
        missing_requirements=missing_requirements,
    )


def build_connector_export_object_store(
    settings: Settings,
    *,
    s3_client_factory: Callable[..., S3PutObjectClient] = _s3_client_factory,
) -> ObjectStore:
    adapter = settings.connector_export_object_store_adapter.strip().casefold()
    if adapter == LOCAL_FILESYSTEM_ADAPTER:
        return LocalObjectStore(settings.connector_export_object_store_root)
    if adapter != S3_COMPATIBLE_ADAPTER:
        raise ObjectStoreConfigurationError(
            f"Unsupported connector export object-store adapter: {adapter}"
        )

    readiness = build_object_store_readiness(settings)
    if not readiness.production_ready:
        missing = ", ".join(readiness.missing_requirements)
        raise ObjectStoreConfigurationError(
            f"S3-compatible object storage is missing required configuration: {missing}."
        )
    endpoint, secure = _normalize_s3_endpoint(
        settings.connector_export_s3_endpoint or "",
        settings.connector_export_s3_secure_transport,
    )
    client = s3_client_factory(
        endpoint=endpoint,
        access_key=settings.connector_export_s3_access_key,
        secret_key=settings.connector_export_s3_secret_key,
        secure=secure,
        region=settings.connector_export_s3_region,
    )
    return S3CompatibleObjectStore(
        client=client,
        bucket_name=settings.connector_export_s3_bucket or "",
        retention_mode=settings.connector_export_s3_retention_mode,
        retention_days=settings.connector_export_s3_retention_days,
        legal_hold_enabled=settings.connector_export_s3_legal_hold_enabled,
    )
