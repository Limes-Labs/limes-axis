import { getApiBaseUrl } from "./api-status";
import { buildAxisAuthInit, type OidcConsoleSession } from "./oidc-session";
import {
  AXIS_CSRF_HEADER_NAME,
  readCsrfTokenFromCookieHeader,
  shouldAttachCsrfHeader,
} from "./session-csrf";

export class AxisApiError extends Error {
  readonly status: number;
  readonly path: string;
  readonly body: unknown;
  readonly detail: unknown;
  readonly code: string | null;
  readonly reason: string | null;
  readonly requiredPermission: string | null;
  readonly validationIssues: unknown[];
  readonly requestId: string | null;

  constructor(
    path: string,
    status: number,
    options: {
      body?: unknown;
      requestId?: string | null;
    } = {},
  ) {
    const detail = readErrorDetail(options.body);
    super(errorMessage(detail, status));
    this.name = "AxisApiError";
    this.status = status;
    this.path = path;
    this.body = options.body ?? null;
    this.detail = detail;
    this.code = readStringField(detail, "code");
    this.reason = readStringField(detail, "reason");
    this.requiredPermission = readStringField(detail, "required_permission");
    this.validationIssues = Array.isArray(detail) ? detail : [];
    this.requestId = options.requestId ?? null;
  }
}

export class AxisApiDecodeError extends Error {
  readonly path: string;

  constructor(path: string, message: string, options?: ErrorOptions) {
    super(message, options);
    this.name = "AxisApiDecodeError";
    this.path = path;
  }
}

export type AxisJsonDecoder<T> = (value: unknown) => T;

export type AxisFetchOptions = {
  session?: OidcConsoleSession | null;
  signal?: AbortSignal;
  method?: string;
  body?: unknown;
  headers?: HeadersInit;
};

export const AXIS_BROWSER_SESSION_SIGNED_OUT_EVENT = "limes-axis:browser-session-signed-out";

const SESSION_REFRESH_PATH = "/identity/session/refresh";

function browserCookieHeader(): string {
  if (typeof document === "undefined") {
    return "";
  }
  return document.cookie ?? "";
}

function buildRequestInit(
  { session, signal, method = "GET", body, headers }: AxisFetchOptions,
): RequestInit {
  const init = buildAxisAuthInit(
    {
      method,
      signal,
      cache: "no-store",
      credentials: "include",
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
    },
    session ?? null,
  );

  const requestHeaders = new Headers(init.headers);
  if (body !== undefined && !requestHeaders.has("Content-Type")) {
    requestHeaders.set("Content-Type", "application/json");
  }
  if (
    !requestHeaders.has(AXIS_CSRF_HEADER_NAME)
    && shouldAttachCsrfHeader({
      method,
      hasAuthorizationHeader: requestHeaders.has("Authorization"),
    })
  ) {
    const csrfToken = readCsrfTokenFromCookieHeader(browserCookieHeader());
    if (csrfToken) {
      requestHeaders.set(AXIS_CSRF_HEADER_NAME, csrfToken);
    }
  }
  init.headers = requestHeaders;

  return init;
}

function announceBrowserSessionSignedOut(): void {
  if (typeof window !== "undefined" && typeof window.dispatchEvent === "function") {
    window.dispatchEvent(new Event(AXIS_BROWSER_SESSION_SIGNED_OUT_EVENT));
  }
}

let inflightBrowserSessionRefresh: Promise<boolean> | null = null;

async function performBrowserSessionRefresh(): Promise<boolean> {
  const headers = new Headers();
  const csrfToken = readCsrfTokenFromCookieHeader(browserCookieHeader());
  if (csrfToken) {
    headers.set(AXIS_CSRF_HEADER_NAME, csrfToken);
  }

  try {
    const response = await fetch(`${getApiBaseUrl()}${SESSION_REFRESH_PATH}`, {
      cache: "no-store",
      credentials: "include",
      headers,
      method: "POST",
    });
    return response.ok;
  } catch {
    return false;
  }
}

/**
 * Rotate the API-owned browser session once, deduplicating concurrent callers.
 *
 * Multiple 401s from parallel requests share one in-flight POST
 * /identity/session/refresh instead of storming the atomic rotation claim.
 */
export function refreshBrowserSession(): Promise<boolean> {
  if (!inflightBrowserSessionRefresh) {
    inflightBrowserSessionRefresh = performBrowserSessionRefresh().finally(() => {
      inflightBrowserSessionRefresh = null;
    });
  }
  return inflightBrowserSessionRefresh;
}

function shouldAttemptSessionRefresh(
  response: Response,
  init: RequestInit,
  path: string,
): boolean {
  if (response.status !== 401 || path === SESSION_REFRESH_PATH) {
    return false;
  }
  // Bearer-mode requests own their token lifecycle; the cookie refresh
  // endpoint cannot mint bearer credentials for them.
  if (new Headers(init.headers).has("Authorization")) {
    return false;
  }
  // Without the readable CSRF cookie there is no browser session to refresh,
  // so anonymous 401s never trigger refresh attempts.
  return readCsrfTokenFromCookieHeader(browserCookieHeader()) !== null;
}

export async function axisFetch(
  path: string,
  options: AxisFetchOptions = {},
): Promise<Response> {
  const init = buildRequestInit(options);
  const response = await fetch(`${getApiBaseUrl()}${path}`, init);

  if (!shouldAttemptSessionRefresh(response, init, path)) {
    return response;
  }

  const refreshed = await refreshBrowserSession();
  if (!refreshed) {
    announceBrowserSessionSignedOut();
    return response;
  }

  // Retry exactly once. The init is rebuilt so the retried request picks up
  // the rotated CSRF cookie issued by the refresh response.
  const retryInit = buildRequestInit(options);
  const retryResponse = await fetch(`${getApiBaseUrl()}${path}`, retryInit);

  // If the retry is still a cookie-mode 401 (session died between refresh and
  // retry, or the resource still rejects the actor) do not refresh again;
  // converge to the signed-out state so the console re-runs its live queries
  // against /identity/session, matching the refresh-failure path above.
  if (shouldAttemptSessionRefresh(retryResponse, retryInit, path)) {
    announceBrowserSessionSignedOut();
  }
  return retryResponse;
}

export async function axisFetchJson<T>(
  path: string,
  options: AxisFetchOptions = {},
): Promise<T> {
  const response = await axisFetch(path, options);
  const body = await readResponseBody(response);

  if (!response.ok) {
    throw new AxisApiError(path, response.status, {
      body,
      requestId:
        response.headers.get("x-request-id") ?? response.headers.get("x-correlation-id"),
    });
  }

  if (body === null || typeof body === "string") {
    throw new AxisApiDecodeError(path, "Axis API returned an invalid JSON response.");
  }
  return body as T;
}

export async function axisFetchParsedJson<T>(
  path: string,
  decoder: AxisJsonDecoder<T>,
  options: AxisFetchOptions = {},
): Promise<T> {
  const body = await axisFetchJson<unknown>(path, options);
  try {
    return decoder(body);
  } catch (error) {
    throw new AxisApiDecodeError(
      path,
      "Axis API response did not match the expected contract.",
      { cause: error },
    );
  }
}

async function readResponseBody(response: Response): Promise<unknown> {
  const text = await response.text();
  if (!text.trim()) {
    return null;
  }
  try {
    return JSON.parse(text) as unknown;
  } catch {
    return text;
  }
}

function readErrorDetail(body: unknown): unknown {
  return isRecord(body) && "detail" in body ? body.detail : body;
}

function errorMessage(detail: unknown, status: number): string {
  if (typeof detail === "string" && detail.trim()) {
    return detail;
  }
  const message = readStringField(detail, "message");
  return message ?? `Axis API request failed with ${status}`;
}

function readStringField(value: unknown, key: string): string | null {
  if (!isRecord(value)) {
    return null;
  }
  const field = value[key];
  return typeof field === "string" && field.trim() ? field : null;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
