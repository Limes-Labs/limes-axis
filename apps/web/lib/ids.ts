const UUID_V4_TEMPLATE = "10000000-1000-4000-8000-100000000000";

function randomUuidFromGetRandomValues(): string | null {
  const cryptoObject = typeof globalThis !== "undefined" ? globalThis.crypto : undefined;

  if (!cryptoObject || typeof cryptoObject.getRandomValues !== "function") {
    return null;
  }

  const bytes = new Uint8Array(16);
  cryptoObject.getRandomValues(bytes);
  // RFC 4122 version 4 + variant bits.
  bytes[6] = (bytes[6] & 0x0f) | 0x40;
  bytes[8] = (bytes[8] & 0x3f) | 0x80;

  const hex = Array.from(bytes, (byte) => byte.toString(16).padStart(2, "0"));
  return [
    hex.slice(0, 4).join(""),
    hex.slice(4, 6).join(""),
    hex.slice(6, 8).join(""),
    hex.slice(8, 10).join(""),
    hex.slice(10, 16).join(""),
  ].join("-");
}

function randomUuidFromMathRandom(): string {
  return UUID_V4_TEMPLATE.replace(/[018]/g, (character) => {
    const digit = Number(character);
    const random = Math.floor(Math.random() * 16);
    return (digit ^ (random & (15 >> (digit / 4)))).toString(16);
  });
}

/**
 * Generate a UUID that never throws in browsers where `crypto.randomUUID` is
 * unavailable — notably plain-HTTP pages on a non-localhost host, where the
 * Web Crypto `randomUUID` method is not exposed. Prefers the native method,
 * falls back to a `getRandomValues`-based v4, then to `Math.random` as a last
 * resort so callers (e.g. idempotency keys) always get a well-formed id.
 */
export function safeRandomUuid(): string {
  const cryptoObject = typeof globalThis !== "undefined" ? globalThis.crypto : undefined;

  if (cryptoObject && typeof cryptoObject.randomUUID === "function") {
    return cryptoObject.randomUUID();
  }

  return randomUuidFromGetRandomValues() ?? randomUuidFromMathRandom();
}
