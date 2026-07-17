import { z } from "zod";

import {
  nullableStringSchema,
  platformStatusSchema,
  stringArraySchema,
  stringRecordSchema,
} from "./shared";

export const auditEventSchema = z.object({
  audit_event_id: z.string(),
  occurred_at: z.string(),
  tenant_id: z.string(),
  actor_id: z.string(),
  actor_type: z.string(),
  event_type: z.string(),
  category: z.string(),
  domain: z.string(),
  scope: z.string(),
  result: z.string(),
  severity: platformStatusSchema,
  source: z.string(),
  summary: z.string(),
  permission_scope: z.string(),
  data_classification: z.string(),
  related_workflow_id: nullableStringSchema,
  related_approval_id: nullableStringSchema,
  related_agent_id: nullableStringSchema,
  evidence_refs: stringArraySchema,
  payload_preview: stringRecordSchema,
});
