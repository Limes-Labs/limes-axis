import "@testing-library/jest-dom/vitest";

import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

// The suite runs without vitest globals, so testing-library's automatic
// cleanup never registers itself; do it explicitly.
afterEach(() => {
  cleanup();
});
