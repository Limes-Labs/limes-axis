import type { ConsoleStrings } from "@/lib/i18n";
import { strings } from "@/lib/strings";
import type {
  IdentitySessionReadModel,
  ManufacturingOperationsSnapshot,
} from "./platform-overview";
import { OPERATIONS_API_PREFIX } from "./tenant-scope";

export type OperationsArtifactKind =
  | "daily_brief"
  | "quality_risk"
  | "maintenance_risk"
  | "supplier_delay";

export type OperationsArtifactAction = {
  kind: OperationsArtifactKind;
  label: string;
  description: string;
  endpoint: string;
  requiredScopes: string[];
};

export type OperationsArtifactRequestBody = {
  tenant_id: string;
  requested_by: string;
  actor_scopes: string[];
  idempotency_key: string;
  limit: number;
  brief_date?: string;
};

export type OperationsArtifactRequest = {
  action: OperationsArtifactAction;
  endpoint: string;
  body: OperationsArtifactRequestBody;
};

export type OperationsArtifactResponse = {
  tenant_id: string;
  status: string;
  requested_by: string;
  audit_event_id: string | null;
  audit_event_type: string;
  idempotent_replay: boolean;
  source_record_ids: string[];
  brief_id?: string;
  brief_date?: string;
  summary_payload?: { headline?: string };
  scenario_id?: string;
  domain?: string;
  risk_level?: string;
  owner_role?: string;
  workflow_ids?: string[];
  scenario_payload?: { headline?: string };
};

export type OperationsArtifactActionState = {
  action: OperationsArtifactAction;
  canRun: boolean;
  missingScopes: string[];
  reason: string | null;
};

type BuildOperationsArtifactRequestInput = {
  kind: OperationsArtifactKind;
  identitySession: IdentitySessionReadModel | null;
  snapshot: ManufacturingOperationsSnapshot;
};

export class OperationsArtifactRequestError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "OperationsArtifactRequestError";
  }
}

const artifactActionRoutes: Array<Omit<OperationsArtifactAction, "label" | "description">> = [
  {
    kind: "daily_brief",
    endpoint: `${OPERATIONS_API_PREFIX}/operations/daily-brief`,
    requiredScopes: ["briefs:generate", "audit:read", "workflows:read"],
  },
  {
    kind: "quality_risk",
    endpoint: `${OPERATIONS_API_PREFIX}/operations/risk-scenarios/quality`,
    requiredScopes: ["quality:read", "workflows:read", "audit:read"],
  },
  {
    kind: "maintenance_risk",
    endpoint: `${OPERATIONS_API_PREFIX}/operations/risk-scenarios/maintenance`,
    requiredScopes: ["maintenance:read", "workflows:read", "audit:read"],
  },
  {
    kind: "supplier_delay",
    endpoint: `${OPERATIONS_API_PREFIX}/operations/risk-scenarios/supplier-delay`,
    requiredScopes: ["supply:read", "workflows:read", "audit:read"],
  },
];

/** The governed artifact actions, labelled from the active catalogue. */
export function operationsArtifactActions(copy: ConsoleStrings = strings): OperationsArtifactAction[] {
  return artifactActionRoutes.map((route) => ({
    ...route,
    ...copy.labels.operationsArtifacts.actions[route.kind],
  }));
}

export const OPERATIONS_ARTIFACT_ACTIONS: OperationsArtifactAction[] = operationsArtifactActions();

function actionForKind(kind: OperationsArtifactKind, copy: ConsoleStrings): OperationsArtifactAction {
  const action = operationsArtifactActions(copy).find((item) => item.kind === kind);
  if (!action) {
    throw new OperationsArtifactRequestError(`Unsupported operations artifact: ${kind}`);
  }
  return action;
}

function missingScopes(
  action: OperationsArtifactAction,
  identitySession: IdentitySessionReadModel | null,
): string[] {
  const scopes = new Set(identitySession?.scopes ?? []);
  return action.requiredScopes.filter((scope) => !scopes.has(scope));
}

export function getOperationsArtifactActionState(
  kind: OperationsArtifactKind,
  identitySession: IdentitySessionReadModel | null,
  copy: ConsoleStrings = strings,
): OperationsArtifactActionState {
  const action = actionForKind(kind, copy);

  if (!identitySession?.authenticated || !identitySession.actor_id || !identitySession.tenant_id) {
    return {
      action,
      canRun: false,
      missingScopes: action.requiredScopes,
      reason: copy.labels.operationsArtifacts.requiresVerifiedActor,
    };
  }

  const missing = missingScopes(action, identitySession);
  if (missing.length > 0) {
    return {
      action,
      canRun: false,
      missingScopes: missing,
      reason: copy.labels.operationsArtifacts.missingScopes(missing),
    };
  }

  return {
    action,
    canRun: true,
    missingScopes: [],
    reason: null,
  };
}

export function buildOperationsArtifactRequest(
  { kind, identitySession, snapshot }: BuildOperationsArtifactRequestInput,
  copy: ConsoleStrings = strings,
): OperationsArtifactRequest {
  const state = getOperationsArtifactActionState(kind, identitySession, copy);

  if (!state.canRun || !identitySession?.actor_id || !identitySession.tenant_id) {
    throw new OperationsArtifactRequestError(state.reason ?? copy.labels.operationsArtifacts.unavailable);
  }

  const briefDate = snapshot.as_of.slice(0, 10);
  const idempotencyWindow = kind === "daily_brief" ? briefDate : "current";
  const idempotencyKey = [
    identitySession.tenant_id,
    "console",
    kind,
    idempotencyWindow,
    identitySession.actor_id,
  ].join(":");

  const body: OperationsArtifactRequestBody = {
    tenant_id: identitySession.tenant_id,
    requested_by: identitySession.actor_id,
    actor_scopes: identitySession.scopes,
    idempotency_key: idempotencyKey,
    limit: 100,
  };

  if (kind === "daily_brief") {
    body.brief_date = briefDate;
  }

  return {
    action: state.action,
    endpoint: state.action.endpoint,
    body,
  };
}

export function operationsArtifactRecordId(response: OperationsArtifactResponse): string {
  return response.brief_id ?? response.scenario_id ?? response.audit_event_id ?? "artifact";
}

export function operationsArtifactHeadline(
  response: OperationsArtifactResponse,
  copy: ConsoleStrings = strings,
): string {
  return (
    response.summary_payload?.headline
    ?? response.scenario_payload?.headline
    ?? copy.labels.operationsArtifacts.persistedBy(operationsArtifactRecordId(response))
  );
}
