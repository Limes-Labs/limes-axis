import { getApiBaseUrl } from "@/lib/api-status";
import { buildAxisAuthInit, type OidcConsoleSession } from "@/lib/oidc-session";

export class AxisApiError extends Error {
  readonly status: number;
  readonly path: string;

  constructor(path: string, status: number, message?: string) {
    super(message ?? `Axis API request failed with ${status}`);
    this.name = "AxisApiError";
    this.status = status;
    this.path = path;
  }
}

export type AxisFetchOptions = {
  session?: OidcConsoleSession | null;
  signal?: AbortSignal;
  method?: string;
  body?: unknown;
  headers?: HeadersInit;
};

export async function axisFetch(
  path: string,
  { session, signal, method = "GET", body, headers }: AxisFetchOptions = {},
): Promise<Response> {
  const init = buildAxisAuthInit(
    {
      method,
      signal,
      cache: "no-store",
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
    },
    session ?? null,
  );

  if (body !== undefined) {
    const requestHeaders = new Headers(init.headers);
    if (!requestHeaders.has("Content-Type")) {
      requestHeaders.set("Content-Type", "application/json");
    }
    init.headers = requestHeaders;
  }

  return fetch(`${getApiBaseUrl()}${path}`, init);
}

export async function axisFetchJson<T>(
  path: string,
  options: AxisFetchOptions = {},
): Promise<T> {
  const response = await axisFetch(path, options);

  if (!response.ok) {
    throw new AxisApiError(path, response.status);
  }

  return (await response.json()) as T;
}