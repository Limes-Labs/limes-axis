import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTypescript from "eslint-config-next/typescript";

export default defineConfig([
  ...nextVitals,
  ...nextTypescript,
  {
    rules: {
      "no-restricted-imports": [
        "error",
        {
          paths: [
            {
              name: "@/lib/runtime-contracts",
              message: "Import the domain-specific runtime-contracts module to preserve route-level code splitting.",
            },
            {
              name: "./runtime-contracts",
              message: "Import the domain-specific runtime-contracts module to preserve route-level code splitting.",
            },
          ],
        },
      ],
    },
  },
  globalIgnores([".next/**", "out/**", "next-env.d.ts"]),
]);
