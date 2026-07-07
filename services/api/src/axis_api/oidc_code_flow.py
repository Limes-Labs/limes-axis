from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from dataclasses import dataclass
from typing import Any
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.hashes import SHA256
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from axis_api.config import Settings

_HOST_COOKIE_PREFIX = "__Host-"
_REFRESH_TOKEN_AAD = b"axis-oidc-refresh-token"
_REFRESH_TOKEN_NONCE_BYTES = 12
_REFRESH_TOKEN_KEY_INFO = b"axis-oidc-refresh-token-encryption-key/v1"
_REFRESH_TOKEN_KEY_SALT = b"axis-oidc-refresh-token-encryption/v1"
_REFRESH_TOKEN_KEY_MIN_LENGTH = 32


class OidcCodeFlowConfigurationError(ValueError):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class OidcCookieValidationError(ValueError):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class OidcTokenExchangeError(ValueError):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True)
class OidcAuthorizationRequest:
    authorization_url: str
    login_cookie_value: str
    max_age_seconds: int


@dataclass(frozen=True)
class OidcLoginState:
    state: str
    nonce: str
    code_verifier: str
    return_to: str


@dataclass(frozen=True)
class OidcSessionCookie:
    session_id: str
    actor_id: str
    tenant_id: str
    scopes: tuple[str, ...]
    expires_at: int


def authorization_endpoint(settings: Settings) -> str:
    if settings.oidc_authorization_url:
        return settings.oidc_authorization_url
    return f"{settings.oidc_issuer.rstrip('/')}/protocol/openid-connect/auth"


def token_endpoint(settings: Settings) -> str:
    if settings.oidc_token_url:
        return settings.oidc_token_url
    return f"{settings.oidc_issuer.rstrip('/')}/protocol/openid-connect/token"


def end_session_endpoint(settings: Settings) -> str:
    if settings.oidc_end_session_url:
        return settings.oidc_end_session_url
    return f"{settings.oidc_issuer.rstrip('/')}/protocol/openid-connect/logout"


def _host_prefixed_cookie_name(name: str, settings: Settings) -> str:
    if not settings.oidc_session_cookie_secure or not settings.oidc_session_cookie_host_prefix:
        return name
    if name.startswith(_HOST_COOKIE_PREFIX):
        return name
    return f"{_HOST_COOKIE_PREFIX}{name}"


def session_cookie_name(settings: Settings) -> str:
    return _host_prefixed_cookie_name(settings.oidc_session_cookie_name, settings)


def csrf_cookie_name(settings: Settings) -> str:
    return _host_prefixed_cookie_name(settings.oidc_csrf_cookie_name, settings)


def csrf_token_for_session(session_id: str, settings: Settings) -> str:
    return hmac.new(
        _cookie_secret(settings),
        f"oidc-csrf:{session_id}".encode(),
        hashlib.sha256,
    ).hexdigest()


def redirect_uri(settings: Settings) -> str:
    if settings.oidc_redirect_uri:
        return settings.oidc_redirect_uri
    return f"{settings.api_base_url.rstrip('/')}/identity/oidc/callback"


def public_redirect(settings: Settings, return_to: str) -> str:
    return f"{settings.public_base_url.rstrip('/')}{_safe_return_to(return_to)}"


def post_logout_redirect_uri(settings: Settings, return_to: str) -> str:
    if settings.oidc_post_logout_redirect_uri:
        return settings.oidc_post_logout_redirect_uri
    return public_redirect(settings, return_to)


def build_end_session_redirect_url(settings: Settings, return_to: str) -> str:
    if not settings.oidc_client_id:
        raise OidcCodeFlowConfigurationError("missing_oidc_client_id")
    query = urlencode(
        {
            "client_id": settings.oidc_client_id,
            "post_logout_redirect_uri": post_logout_redirect_uri(settings, return_to),
        }
    )
    endpoint = end_session_endpoint(settings)
    separator = "&" if "?" in endpoint else "?"
    return f"{endpoint}{separator}{query}"


def build_authorization_request(settings: Settings, return_to: str) -> OidcAuthorizationRequest:
    _require_code_flow_settings(settings)
    now = int(time.time())
    state = secrets.token_urlsafe(32)
    nonce = secrets.token_urlsafe(32)
    code_verifier = secrets.token_urlsafe(64)
    code_challenge = _code_challenge(code_verifier)
    login_state = {
        "kind": "oidc_login",
        "state": state,
        "nonce": nonce,
        "code_verifier": code_verifier,
        "return_to": _safe_return_to(return_to),
        "expires_at": now + settings.oidc_login_state_ttl_seconds,
    }
    query = urlencode(
        {
            "response_type": "code",
            "client_id": settings.oidc_client_id,
            "redirect_uri": redirect_uri(settings),
            "scope": " ".join(settings.oidc_scopes),
            "state": state,
            "nonce": nonce,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
        }
    )
    return OidcAuthorizationRequest(
        authorization_url=f"{authorization_endpoint(settings)}?{query}",
        login_cookie_value=sign_cookie(login_state, settings),
        max_age_seconds=settings.oidc_login_state_ttl_seconds,
    )


def read_login_state(cookie_value: str | None, settings: Settings) -> OidcLoginState:
    payload = verify_cookie(cookie_value, settings, expected_kind="oidc_login")
    return OidcLoginState(
        state=str(payload["state"]),
        nonce=str(payload["nonce"]),
        code_verifier=str(payload["code_verifier"]),
        return_to=_safe_return_to(str(payload["return_to"])),
    )


def build_token_exchange_form(
    *,
    settings: Settings,
    code: str,
    login_state: OidcLoginState,
) -> dict[str, str]:
    if not code:
        raise OidcTokenExchangeError("missing_code")
    form = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri(settings),
        "client_id": settings.oidc_client_id or "",
        "code_verifier": login_state.code_verifier,
    }
    if settings.oidc_client_secret:
        form["client_secret"] = settings.oidc_client_secret
    return form


def build_refresh_token_form(*, settings: Settings, refresh_token: str) -> dict[str, str]:
    if not refresh_token:
        raise OidcTokenExchangeError("missing_refresh_token")
    form = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": settings.oidc_client_id or "",
    }
    if settings.oidc_client_secret:
        form["client_secret"] = settings.oidc_client_secret
    return form


def _refresh_token_key(settings: Settings) -> bytes:
    value = settings.oidc_refresh_token_encryption_key
    if not value:
        raise OidcCodeFlowConfigurationError("missing_refresh_token_encryption_key")
    if len(value) < _REFRESH_TOKEN_KEY_MIN_LENGTH:
        raise OidcCodeFlowConfigurationError("weak_refresh_token_encryption_key")
    kdf = HKDF(
        algorithm=SHA256(),
        length=32,
        salt=_REFRESH_TOKEN_KEY_SALT,
        info=_REFRESH_TOKEN_KEY_INFO,
    )
    return kdf.derive(value.encode("utf-8"))


def refresh_token_encryption_key_is_strong(settings: Settings) -> bool:
    value = settings.oidc_refresh_token_encryption_key
    return bool(value) and len(value) >= _REFRESH_TOKEN_KEY_MIN_LENGTH


def validate_refresh_token_encryption_key(settings: Settings) -> None:
    """Fail fast at startup when a refresh-token key is set but too weak."""
    value = settings.oidc_refresh_token_encryption_key
    if value and len(value) < _REFRESH_TOKEN_KEY_MIN_LENGTH:
        raise OidcCodeFlowConfigurationError("weak_refresh_token_encryption_key")


def encrypt_refresh_token(refresh_token: str, settings: Settings) -> str:
    if not refresh_token:
        raise OidcTokenExchangeError("missing_refresh_token")
    key = _refresh_token_key(settings)
    nonce = secrets.token_bytes(_REFRESH_TOKEN_NONCE_BYTES)
    ciphertext = AESGCM(key).encrypt(
        nonce,
        refresh_token.encode("utf-8"),
        _REFRESH_TOKEN_AAD,
    )
    return _b64url(nonce + ciphertext)


def decrypt_refresh_token(ciphertext_value: str, settings: Settings) -> str:
    key = _refresh_token_key(settings)
    try:
        raw = _b64url_decode(ciphertext_value)
        nonce = raw[:_REFRESH_TOKEN_NONCE_BYTES]
        ciphertext = raw[_REFRESH_TOKEN_NONCE_BYTES:]
        return AESGCM(key).decrypt(nonce, ciphertext, _REFRESH_TOKEN_AAD).decode("utf-8")
    except (InvalidTag, ValueError) as exc:
        raise OidcTokenExchangeError("refresh_token_unreadable") from exc


def exchange_authorization_code(form: dict[str, str], settings: Settings) -> dict[str, Any]:
    body = urlencode(form).encode("utf-8")
    request = Request(
        token_endpoint(settings),
        data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=5) as response:
            payload = json.loads(response.read())
    except (OSError, URLError, ValueError) as exc:
        raise OidcTokenExchangeError("token_exchange_failed") from exc
    if not isinstance(payload, dict):
        raise OidcTokenExchangeError("invalid_token_response")
    return payload


def session_cookie_from_principal(
    token_response: dict[str, Any],
    principal: Any,
    settings: Settings,
    *,
    session_id: str | None = None,
    max_age_ceiling: int | None = None,
) -> tuple[str, int, str]:
    resolved_session_id = session_id or secrets.token_urlsafe(48)
    expires_in = token_response.get("expires_in")
    max_age = settings.oidc_session_cookie_ttl_seconds
    if isinstance(expires_in, int) and expires_in > 0:
        max_age = min(max_age, expires_in)
    now = int(time.time())
    if isinstance(getattr(principal, "expires_at", None), int):
        token_remaining_seconds = principal.expires_at - now
        if token_remaining_seconds <= 0:
            raise OidcTokenExchangeError("expired_access_token")
        max_age = min(max_age, token_remaining_seconds)
    if max_age_ceiling is not None:
        if max_age_ceiling <= 0:
            raise OidcTokenExchangeError("expired_session_absolute_lifetime")
        max_age = min(max_age, max_age_ceiling)
    if max_age <= 0:
        raise OidcTokenExchangeError("invalid_session_ttl")
    expires_at = now + max_age
    payload = {
        "kind": "oidc_session",
        "session_id": resolved_session_id,
        "actor_id": principal.actor_id,
        "tenant_id": principal.tenant_id,
        "scopes": list(principal.scopes),
        "expires_at": expires_at,
    }
    return sign_cookie(payload, settings), max_age, resolved_session_id


def read_session_cookie(cookie_value: str | None, settings: Settings) -> OidcSessionCookie:
    payload = verify_cookie(cookie_value, settings, expected_kind="oidc_session")
    scopes = payload.get("scopes", [])
    if not isinstance(scopes, list):
        raise OidcCookieValidationError("invalid_session_scopes")
    session_id = payload.get("session_id")
    if not isinstance(session_id, str) or len(session_id) < 32:
        raise OidcCookieValidationError("invalid_session_id")
    return OidcSessionCookie(
        session_id=session_id,
        actor_id=str(payload["actor_id"]),
        tenant_id=str(payload["tenant_id"]),
        scopes=tuple(str(scope) for scope in scopes if scope),
        expires_at=int(payload["expires_at"]),
    )


def session_id_hash(session_id: str, settings: Settings) -> str:
    return hmac.new(
        _cookie_secret(settings),
        f"oidc-session:{session_id}".encode(),
        hashlib.sha256,
    ).hexdigest()


def sign_cookie(payload: dict[str, Any], settings: Settings) -> str:
    secret = _cookie_secret(settings)
    encoded_payload = _b64url(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signature = _b64url(hmac.new(secret, encoded_payload.encode("ascii"), hashlib.sha256).digest())
    return f"{encoded_payload}.{signature}"


def verify_cookie(
    cookie_value: str | None,
    settings: Settings,
    *,
    expected_kind: str,
) -> dict[str, Any]:
    if not cookie_value:
        raise OidcCookieValidationError("missing_cookie")
    secret = _cookie_secret(settings)
    encoded_payload, separator, encoded_signature = cookie_value.partition(".")
    if not separator or not encoded_payload or not encoded_signature:
        raise OidcCookieValidationError("invalid_cookie")
    expected_signature = _b64url(
        hmac.new(secret, encoded_payload.encode("ascii"), hashlib.sha256).digest()
    )
    if not hmac.compare_digest(encoded_signature, expected_signature):
        raise OidcCookieValidationError("invalid_cookie_signature")
    try:
        payload = json.loads(_b64url_decode(encoded_payload))
    except (ValueError, json.JSONDecodeError) as exc:
        raise OidcCookieValidationError("invalid_cookie_payload") from exc
    if not isinstance(payload, dict) or payload.get("kind") != expected_kind:
        raise OidcCookieValidationError("invalid_cookie_kind")
    expires_at = payload.get("expires_at")
    if not isinstance(expires_at, int) or expires_at <= int(time.time()):
        raise OidcCookieValidationError("expired_cookie")
    return payload


def _require_code_flow_settings(settings: Settings) -> None:
    if not settings.oidc_client_id:
        raise OidcCodeFlowConfigurationError("missing_oidc_client_id")
    _cookie_secret(settings)


def _cookie_secret(settings: Settings) -> bytes:
    value = settings.oidc_session_cookie_signing_secret
    if not value:
        raise OidcCodeFlowConfigurationError("missing_session_cookie_signing_secret")
    return value.encode("utf-8")


def _code_challenge(code_verifier: str) -> str:
    digest = hashlib.sha256(code_verifier.encode("ascii")).digest()
    return _b64url(digest)


def _safe_return_to(value: str) -> str:
    if not value.startswith("/") or value.startswith("//") or "\\" in value:
        return "/"
    return value


def _b64url(payload: bytes) -> str:
    return base64.urlsafe_b64encode(payload).rstrip(b"=").decode("ascii")


def _b64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(f"{value}{padding}".encode("ascii"))
