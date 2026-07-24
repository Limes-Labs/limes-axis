import { defineConfig } from "vitest/config";
import path from "node:path";

const alias = {
  "@": path.resolve(import.meta.dirname),
};

export default defineConfig({
  test: {
    // jsdom suites are interaction-heavy; bounding concurrency keeps their
    // five-second per-test budget stable on both developer laptops and CI.
    maxWorkers: 4,
    projects: [
      {
        resolve: { alias },
        test: {
          name: "node",
          environment: "node",
          include: ["**/*.test.ts"],
        },
      },
      {
        resolve: { alias },
        test: {
          name: "jsdom",
          environment: "jsdom",
          include: ["**/*.test.tsx"],
          setupFiles: ["./vitest.setup.ts"],
        },
      },
    ],
  },
});
