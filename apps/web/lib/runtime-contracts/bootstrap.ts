import { z } from "zod";

import type { DemoBootstrapResult } from "../use-demo-bootstrap";
import { parseContract } from "./shared";

const demoBootstrapResult = z.object({
  tenant_id: z.string(),
  scenario: z.string(),
  plant_name: z.string(),
  bootstrapped: z.boolean(),
  surfaces: z.array(z.object({
    surface: z.string(),
    reference_id: z.string(),
    state: z.enum(["created", "existing"]),
  })),
  audit_event_id: z.string(),
  idempotent_replay: z.boolean(),
});

export function parseDemoBootstrapResult(value: unknown): DemoBootstrapResult {
  return parseContract(demoBootstrapResult, value);
}
