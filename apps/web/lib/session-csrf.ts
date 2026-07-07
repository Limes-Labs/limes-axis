export const AXIS_CSRF_HEADER_NAME = "X-Axis-Csrf-Token";
export const AXIS_CSRF_COOKIE_NAME = "axis_csrf";
export const AXIS_CSRF_HOST_COOKIE_NAME = "__Host-axis_csrf";

const SAFE_METHODS = new Set(["GET", "HEAD", "OPTIONS", "TRACE"]);

function decodeCookieValue(value: string): string {
  try {
    return decodeURIComponent(value);
  } catch {
    return value;
  }
}

function parseCookieHeader(cookieHeader: string): Map<string, string> {
  const cookies = new Map<string, string>();
  for (const pair of cookieHeader.split(";")) {
    const separatorIndex = pair.indexOf("=");
    if (separatorIndex <= 0) {
      continue;
    }
    const name = pair.slice(0, separatorIndex).trim();
    const value = pair.slice(separatorIndex + 1).trim();
    if (name && !cookies.has(name)) {
      cookies.set(name, decodeCookieValue(value));
    }
  }
  return cookies;
}

/**
 * Read the API-issued double-submit CSRF token from the readable CSRF cookie.
 *
 * Secure deployments rename the cookie to a `__Host-` prefixed name
 * (AXIS_OIDC_SESSION_COOKIE_HOST_PREFIX), so that variant wins when both
 * exist. Returns null when no browser session CSRF cookie is present.
 */
export function readCsrfTokenFromCookieHeader(cookieHeader: string): string | null {
  if (!cookieHeader) {
    return null;
  }
  const cookies = parseCookieHeader(cookieHeader);
  return (
    cookies.get(AXIS_CSRF_HOST_COOKIE_NAME) ?? cookies.get(AXIS_CSRF_COOKIE_NAME) ?? null
  );
}

export function isStateChangingMethod(method: string): boolean {
  return !SAFE_METHODS.has(method.toUpperCase());
}

/**
 * Decide whether a console request must carry the CSRF header.
 *
 * Only cookie-session mutations need it: safe methods never mutate state and
 * bearer requests are CSRF-exempt server-side because they carry no ambient
 * cookie authority.
 */
export function shouldAttachCsrfHeader({
  method,
  hasAuthorizationHeader,
}: {
  method: string;
  hasAuthorizationHeader: boolean;
}): boolean {
  return isStateChangingMethod(method) && !hasAuthorizationHeader;
}
