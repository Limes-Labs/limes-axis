import { describe, expect, it } from "vitest";

import nextConfig from "../next.config";

describe("Next.js demo configuration", () => {
  it("allows the in-app Browser 127.0.0.1 origin during local demo development", () => {
    expect(nextConfig.allowedDevOrigins).toContain("127.0.0.1");
  });
});
