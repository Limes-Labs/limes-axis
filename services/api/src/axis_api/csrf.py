from __future__ import annotations

import hmac

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp

from axis_api.config import Settings
from axis_api.errors import AxisErrorCode
from axis_api.oidc_code_flow import (
    OidcCodeFlowConfigurationError,
    OidcCookieValidationError,
    csrf_token_for_session,
    read_session_cookie,
    session_cookie_name,
)

CSRF_HEADER_NAME = "x-axis-csrf-token"
_SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS", "TRACE"})


class BrowserSessionCsrfMiddleware(BaseHTTPMiddleware):
    """Enforce a double-submit CSRF token for cookie-authenticated mutations.

    The check applies to every state-changing request that authenticates through
    the Axis session cookie. Requests carrying an ``Authorization`` bearer header
    are exempt because they do not rely on ambient cookie authority, and safe
    methods (GET/HEAD/OPTIONS) never mutate state. The expected token is an HMAC
    of the session id under the cookie-signing key, so no CSRF state is stored
    server-side.
    """

    def __init__(self, app: ASGIApp, *, settings: Settings) -> None:
        super().__init__(app)
        self.settings = settings

    async def dispatch(self, request: Request, call_next) -> Response:
        rejection = self._csrf_rejection(request)
        if rejection is not None:
            return rejection
        return await call_next(request)

    def _csrf_rejection(self, request: Request) -> JSONResponse | None:
        if request.method.upper() in _SAFE_METHODS:
            return None
        if request.headers.get("authorization"):
            return None
        session_cookie = request.cookies.get(session_cookie_name(self.settings))
        if not session_cookie:
            return None
        try:
            oidc_session = read_session_cookie(session_cookie, self.settings)
        except (OidcCodeFlowConfigurationError, OidcCookieValidationError):
            # An unreadable cookie cannot authenticate the request, so the
            # downstream principal resolver will reject it; do not add a
            # confusing CSRF error on top of an invalid-session error.
            return None
        provided_token = request.headers.get(CSRF_HEADER_NAME)
        if not provided_token:
            return _csrf_error(
                "A CSRF token header is required for browser session mutations.",
                "csrf_token_required",
            )
        expected_token = csrf_token_for_session(oidc_session.session_id, self.settings)
        # Compare as bytes: hmac.compare_digest raises TypeError for str
        # operands containing non-ASCII characters, and the header value is
        # attacker-controlled. UTF-8 encoding never fails for a str.
        if not hmac.compare_digest(
            provided_token.encode("utf-8"), expected_token.encode("utf-8")
        ):
            return _csrf_error(
                "The CSRF token does not match the browser session.",
                "csrf_token_mismatch",
            )
        return None


def _csrf_error(message: str, reason: str) -> JSONResponse:
    return JSONResponse(
        status_code=403,
        content={
            "detail": {
                "code": AxisErrorCode.PERMISSION_DENIED.value,
                "message": message,
                "reason": reason,
            }
        },
    )
