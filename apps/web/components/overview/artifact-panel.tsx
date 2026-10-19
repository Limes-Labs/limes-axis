"use client";

import { useState } from "react";
import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";
import { AlertTriangle, FileCheck2, ShieldCheck } from "lucide-react";

import { Button, buttonVariants } from "@/components/ui/button";
import { SsoSignInLink } from "@/components/sso-sign-in-link";
import { Card } from "@/components/ui/card";
import { ErrorPanel, LoadingPanel } from "@/components/ui/states";
import {
  axisFetchParsedJson,
  toAxisOperatorError,
  type AxisOperatorError,
} from "@/lib/axis-api";
import { buildOidcAuthorizeUrl } from "@/lib/oidc-session";
import {
  buildOperationsArtifactRequest,
  getOperationsArtifactActionState,
  operationsArtifactHeadline,
  operationsArtifactRecordId,
  OPERATIONS_ARTIFACT_ACTIONS,
  type OperationsArtifactKind,
  type OperationsArtifactResponse,
} from "@/lib/operations-artifacts";
import {
  platformStatusClass,
  type ManufacturingOperationsSnapshot,
} from "@/lib/platform-overview";
import { useStrings } from "@/providers/locale-provider";
import {
  parseOperationsArtifactResponse,
} from "@/lib/runtime-contracts/overview";
import { useOidcConsoleSession } from "@/lib/use-oidc-session";
import { useConsole } from "@/providers/console-provider";

import { buildAuditEventHref } from "@/lib/audit-demo";
import { PanelHeader, StatusDot, type OverviewQuery } from "./overview-shared";
import { OPERATIONS_API_PREFIX } from "@/lib/tenant-scope";
import { useIdentitySession } from "@/lib/use-identity-session";

/*
 * Compact governed-evidence generation panel: one card, one action row, the
 * persisted result inline. The SSO banner only renders when the identity API
 * has confirmed the browser session is unauthenticated — a missing identity
 * endpoint just leaves the actions disabled with their scope reason.
 */

export const SNAPSHOT_ENDPOINT = `${OPERATIONS_API_PREFIX}/operations/snapshot`;

const ACTION_ICONS: Record<string, typeof FileCheck2> = {
  daily_brief: FileCheck2,
  supplier_delay: AlertTriangle,
};

export function ArtifactPanel({
  snapshot,
  onArtifactCommitted,
}: {
  snapshot: OverviewQuery<ManufacturingOperationsSnapshot>;
  onArtifactCommitted: () => void;
}) {
  const strings = useStrings();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const { apiBaseUrl } = useConsole();
  const { session } = useOidcConsoleSession();
  const identity = useIdentitySession();
  const identitySession = identity.data;
  const identitySessionUnavailable = identity.isUnavailable;
  const [pendingKind, setPendingKind] = useState<OperationsArtifactKind | null>(null);
  const [artifact, setArtifact] = useState<{
    actionLabel: string;
    response: OperationsArtifactResponse;
  } | null>(null);
  const [error, setError] = useState<AxisOperatorError | null>(null);
  const copy = strings.overview.artifact;

  if (!snapshot.data) {
    if (snapshot.source === "loading") {
      return <LoadingPanel layout="detail" />;
    }

    return (
      <ErrorPanel
        detail={copy.error.detail}
        endpoint={SNAPSHOT_ENDPOINT}
        reference={snapshot.errorRequestId ?? undefined}
        title={copy.error.title}
      />
    );
  }

  const operationsSnapshot = snapshot.data;
  const sessionStatus = identitySession?.authenticated ? "ready" : "watch";
  const sessionLabel = identitySession?.authenticated
    ? "API-verified actor"
    : identitySessionUnavailable
      ? "Identity API required"
      : "OIDC session required";
  const returnTo = `${pathname}${searchParams.toString() ? `?${searchParams.toString()}` : ""}`;
  const signInUrl = buildOidcAuthorizeUrl(apiBaseUrl, returnTo);
  // The SSO banner needs a confirmed unauthenticated session, not a missing
  // identity endpoint.
  const showSsoGate = identitySession !== null && !identitySession.authenticated;

  async function submitArtifact(kind: OperationsArtifactKind) {
    setPendingKind(kind);
    setError(null);

    try {
      const request = buildOperationsArtifactRequest({
        kind,
        identitySession,
        snapshot: operationsSnapshot,
      });
      const response = await axisFetchParsedJson<OperationsArtifactResponse>(
        request.endpoint,
        parseOperationsArtifactResponse,
        { method: "POST", session, body: request.body },
      );

      setArtifact({ actionLabel: request.action.label, response });
      onArtifactCommitted();
    } catch (caught) {
      setError(toAxisOperatorError(
        caught,
        "Axis could not persist the operations artifact.",
      ));
    } finally {
      setPendingKind(null);
    }
  }

  return (
    <Card className="grid content-start gap-4">
      <PanelHeader
        aside={
          <span className={`status-pill ${platformStatusClass(sessionStatus)}`}>
            {sessionLabel}
          </span>
        }
        eyebrow={copy.eyebrow}
        title={copy.title}
      />
      <p className="m-0 max-w-3xl text-sm text-muted">{copy.description}</p>

      {showSsoGate ? (
        <div className="flex flex-wrap items-center gap-3 rounded-2xl border border-signal/30 bg-tint-50 p-4 dark:bg-signal/10">
          <ShieldCheck className="shrink-0 text-signal" size={18} />
          <div className="grid min-w-0 flex-1 gap-0.5">
            <p className="m-0 text-sm font-medium text-ink">{copy.ssoTitle}</p>
            <p className="m-0 text-xs text-muted">{copy.ssoDetail}</p>
          </div>
          <SsoSignInLink
            className={buttonVariants({ size: "lg" })}
            href={signInUrl}
          >
            {copy.signIn}
          </SsoSignInLink>
        </div>
      ) : null}

      <div className="flex flex-wrap gap-2" role="group" aria-label={strings.ui.overviewArtifactPanel.governedArtifactActions}>
        {OPERATIONS_ARTIFACT_ACTIONS.map((action) => {
          const state = getOperationsArtifactActionState(action.kind, identitySession);
          const pending = pendingKind === action.kind;
          const Icon = ACTION_ICONS[action.kind] ?? ShieldCheck;

          return (
            <Button
              aria-describedby={`${action.kind}-artifact-state`}
              size="sm"
              variant="secondary"
              disabled={!state.canRun || Boolean(pendingKind)}
              key={action.kind}
              onClick={() => void submitArtifact(action.kind)}
              title={state.reason ?? action.description}
              type="button"
            >
              <Icon aria-hidden="true" size={14} />
              {pending ? strings.ui.overviewArtifactPanel.persisting : action.label}
              <span className="sr-only" id={`${action.kind}-artifact-state`}>
                {state.reason ?? action.description}
              </span>
            </Button>
          );
        })}
      </div>

      {artifact ? (
        <div
          className="flex flex-wrap items-start gap-3 rounded-2xl border border-positive/35 bg-positive/8 p-4"
          role="status"
        >
          <StatusDot status="ready" />
          <div className="grid min-w-0 flex-1 gap-1">
            <p className="m-0 font-mono text-sm break-words text-ink">
              {artifact.actionLabel} / {operationsArtifactRecordId(artifact.response)}
            </p>
            <p className="m-0 text-xs text-muted">{operationsArtifactHeadline(artifact.response)}</p>
            <div className="flex flex-wrap gap-x-4 gap-y-1 font-mono text-[11px] text-muted">
              <span>{artifact.response.idempotent_replay ? strings.ui.overviewArtifactPanel.idempotentReplay : strings.ui.overviewArtifactPanel.created}</span>
              <span>{artifact.response.source_record_ids.length} source records</span>
              <span>{artifact.response.audit_event_type}</span>
            </div>
          </div>
          {artifact.response.audit_event_id ? (
            <Link
              className={buttonVariants({ size: "sm", variant: "link" })}
              href={buildAuditEventHref(artifact.response.audit_event_id)}
            >
              {strings.ui.common.openAudit}
            </Link>
          ) : null}
        </div>
      ) : null}

      {error ? (
        <ErrorPanel
          detail={error.message}
          reference={error.requestId ?? undefined}
          title={strings.ui.overviewArtifactPanel.artifactPersistenceFailed}
        />
      ) : null}
    </Card>
  );
}
