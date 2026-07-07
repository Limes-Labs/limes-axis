import { describe, expect, it } from "vitest";

import {
  AXIS_CSRF_COOKIE_NAME,
  AXIS_CSRF_HEADER_NAME,
  AXIS_CSRF_HOST_COOKIE_NAME,
  isStateChangingMethod,
  readCsrfTokenFromCookieHeader,
  shouldAttachCsrfHeader,
} from "./session-csrf";

describe("browser session CSRF helpers", () => {
  it("matches the API middleware header and cookie contract", () => {
    expect(AXIS_CSRF_HEADER_NAME).toBe("X-Axis-Csrf-Token");
    expect(AXIS_CSRF_COOKIE_NAME).toBe("axis_csrf");
    expect(AXIS_CSRF_HOST_COOKIE_NAME).toBe("__Host-axis_csrf");
  });

  it("reads the CSRF token from the readable cookie", () => {
    expect(readCsrfTokenFromCookieHeader("axis_csrf=abc123")).toBe("abc123");
    expect(
      readCsrfTokenFromCookieHeader("other=1; axis_csrf=abc123; theme=dark"),
    ).toBe("abc123");
  });

  it("prefers the __Host- prefixed cookie used by secure profiles", () => {
    expect(
      readCsrfTokenFromCookieHeader("axis_csrf=plain; __Host-axis_csrf=hardened"),
    ).toBe("hardened");
  });

  it("decodes URL-encoded cookie values", () => {
    expect(readCsrfTokenFromCookieHeader("axis_csrf=a%3Db")).toBe("a=b");
  });

  it("returns null when no CSRF cookie is present", () => {
    expect(readCsrfTokenFromCookieHeader("")).toBeNull();
    expect(readCsrfTokenFromCookieHeader("session=value; theme=dark")).toBeNull();
    expect(readCsrfTokenFromCookieHeader("axis_csrf")).toBeNull();
  });

  it("treats only unsafe methods as state changing", () => {
    expect(isStateChangingMethod("GET")).toBe(false);
    expect(isStateChangingMethod("head")).toBe(false);
    expect(isStateChangingMethod("OPTIONS")).toBe(false);
    expect(isStateChangingMethod("POST")).toBe(true);
    expect(isStateChangingMethod("put")).toBe(true);
    expect(isStateChangingMethod("DELETE")).toBe(true);
  });

  it("attaches the header only for cookie-mode mutations", () => {
    expect(
      shouldAttachCsrfHeader({ method: "POST", hasAuthorizationHeader: false }),
    ).toBe(true);
    expect(
      shouldAttachCsrfHeader({ method: "POST", hasAuthorizationHeader: true }),
    ).toBe(false);
    expect(
      shouldAttachCsrfHeader({ method: "GET", hasAuthorizationHeader: false }),
    ).toBe(false);
  });
});
