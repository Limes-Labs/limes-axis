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


BROWSER_SESSION_TOUCH_INTERVAL_SECONDS = 60.0


def browser_session_touch_due(
    stored_session: OidcBrowserSession,
    settings: Settings,
    now: datetime,
) -> bool:
    """Whether a cookie request should rewrite ``last_seen_at``.

    Writing the row on every cookie-authenticated request turned each read
    into an UPDATE. Activity is recorded at most once per interval: 60 s, or a
    tenth of the idle timeout when that is shorter, so idle expiry can fire at
    most that much earlier than the true last activity.
    """
    interval = BROWSER_SESSION_TOUCH_INTERVAL_SECONDS
    if settings.oidc_session_idle_timeout_seconds > 0:
        interval = min(interval, settings.oidc_session_idle_timeout_seconds / 10)
    if stored_session.last_seen_at is None:
        return True
    elapsed = now - ensure_aware_datetime(stored_session.last_seen_at)
    return elapsed >= timedelta(seconds=interval)


def browser_session_is_active(
    stored_session: OidcBrowserSession,
    settings: Settings,
) -> bool:
    return browser_session_lifecycle_failure(stored_session, settings) is None
