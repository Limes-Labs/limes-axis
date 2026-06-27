import hashlib
import json
from pathlib import Path, PurePosixPath
from typing import Protocol

from pydantic import BaseModel, Field


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


class LocalObjectStore:
    adapter_name = "local_filesystem"
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
