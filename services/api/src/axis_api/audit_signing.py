import hashlib
import hmac
import json
from typing import Protocol

from pydantic import BaseModel, Field


class AuditLedgerSignatureProof(BaseModel):
    algorithm: str = Field(min_length=1)
    key_id: str | None = None
    signing_mode: str = Field(min_length=1)
    verification_status: str = Field(min_length=1)
    signed_payload_sha256: str = Field(min_length=64, max_length=64)
    signature: str | None = None
    notes: list[str] = Field(default_factory=list)


class AuditLedgerSigner(Protocol):
    key_id: str
    algorithm: str

    def sign_payload(self, payload: dict) -> AuditLedgerSignatureProof:
        pass


def canonical_ledger_signature_payload(
    manifest: BaseModel,
    integrity_proof: BaseModel,
) -> dict:
    return {
        "manifest": manifest.model_dump(mode="json"),
        "integrity_proof": integrity_proof.model_dump(mode="json"),
    }


def _canonical_json(payload: dict) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def _payload_digest(payload: dict) -> str:
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


class SelfHostedAuditLedgerSigner:
    algorithm = "hmac-sha256"

    def __init__(self, key_id: str, secret_key: str) -> None:
        if not key_id:
            raise ValueError("Audit ledger signing key id is required")
        if not secret_key:
            raise ValueError("Audit ledger signing secret key is required")
        self.key_id = key_id
        self._secret_key = secret_key.encode("utf-8")

    def sign_payload(self, payload: dict) -> AuditLedgerSignatureProof:
        encoded_payload = _canonical_json(payload).encode("utf-8")
        signature = hmac.new(
            self._secret_key,
            encoded_payload,
            hashlib.sha256,
        ).hexdigest()
        return AuditLedgerSignatureProof(
            algorithm=self.algorithm,
            key_id=self.key_id,
            signing_mode="self_hosted_hmac",
            verification_status="verified",
            signed_payload_sha256=hashlib.sha256(encoded_payload).hexdigest(),
            signature=signature,
            notes=[
                "Ledger signature covers the export manifest and hash-chain integrity proof.",
                "Secret material is not exported with the proof.",
            ],
        )


def unsigned_audit_ledger_signature(payload: dict) -> AuditLedgerSignatureProof:
    return AuditLedgerSignatureProof(
        algorithm="unsigned",
        key_id=None,
        signing_mode="not_configured",
        verification_status="unsigned",
        signed_payload_sha256=_payload_digest(payload),
        signature=None,
        notes=[
            "Audit ledger signing key is not configured.",
            "Hash-chain integrity proof is present, but no KMS/self-hosted signature was produced.",
        ],
    )


def verify_audit_ledger_signature(
    manifest: BaseModel,
    integrity_proof: BaseModel,
    signature_proof: AuditLedgerSignatureProof,
    *,
    secret_key: str,
) -> bool:
    if (
        signature_proof.algorithm != SelfHostedAuditLedgerSigner.algorithm
        or signature_proof.signature is None
        or not secret_key
    ):
        return False
    payload = canonical_ledger_signature_payload(manifest, integrity_proof)
    encoded_payload = _canonical_json(payload).encode("utf-8")
    expected_signature = hmac.new(
        secret_key.encode("utf-8"),
        encoded_payload,
        hashlib.sha256,
    ).hexdigest()
    expected_digest = hashlib.sha256(encoded_payload).hexdigest()
    return hmac.compare_digest(
        signature_proof.signature,
        expected_signature,
    ) and hmac.compare_digest(
        signature_proof.signed_payload_sha256,
        expected_digest,
    )
