"""Pure OIDC browser-session lifecycle checks shared by auth boundaries."""

from datetime import UTC, datetime, timedelta

from axis_api.config import Settings
from axis_api.models import OidcBrowserSession


def ensure_aware_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


def browser_session_lifecycle_failure(
    stored_session: OidcBrowserSession,
    settings: Settings,
) -> tuple[str, str] | None:
    now = datetime.now(UTC)
    if stored_session.status == "refreshing":
        claim_deadline = ensure_aware_datetime(stored_session.updated_at) + timedelta(
            seconds=settings.oidc_refresh_claim_staleness_seconds
        )
        if claim_deadline <= now:
            return ("revoked_session_cookie", "refresh_claim_orphaned")
        return ("revoked_session_cookie", "")
    if stored_session.status != "active":
        return ("revoked_session_cookie", "")
    if ensure_aware_datetime(stored_session.expires_at) <= now:
        return ("expired_session_cookie", "session_expired")
    if (
        stored_session.absolute_expires_at is not None
        and ensure_aware_datetime(stored_session.absolute_expires_at) <= now
    ):
        return ("expired_session_cookie", "absolute_timeout")
    idle_timeout_seconds = settings.oidc_session_idle_timeout_seconds
    if idle_timeout_seconds > 0:
        last_activity = stored_session.last_seen_at or stored_session.created_at
        idle_deadline = ensure_aware_datetime(last_activity) + timedelta(
            seconds=idle_timeout_seconds
        )
        if idle_deadline <= now:
            return ("idle_session_timeout", "idle_timeout")
    return None


def browser_session_is_active(
    stored_session: OidcBrowserSession,
    settings: Settings,
) -> bool:
    return browser_session_lifecycle_failure(stored_session, settings) is None
