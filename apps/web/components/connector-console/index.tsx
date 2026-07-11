"use client";

import { useMemo, useState } from "react";
import { Cable, Plus } from "lucide-react";

import { Button } from "@/components/ui/button";
import { MasterDetail } from "@/components/ui/master-detail";
import { MetricStrip, type Metric } from "@/components/ui/metric-strip";
import { EmptyPanel, ErrorPanel, LoadingPanel } from "@/components/ui/states";
import {
  mergeConnectorListEntries,
  pendingProposalCount,
  type ConnectorListEntry,
} from "@/lib/connectors-console";
import { platformStatusClass, platformStatusLabel } from "@/lib/platform-overview";
import { strings } from "@/lib/strings";
import {
  CONNECTOR_ENDPOINTS,
  useConnectorRegistries,
  type ConnectorRegistries,
} from "@/lib/use-connector-registries";
import { useConsole } from "@/providers/console-provider";

import { AddConnectorWizard } from "./add-connector-wizard";
import { ConnectorDetail } from "./detail";
import { ConnectorList } from "./list";

/*
 * Connector console orchestrator: five user-relevant metrics, a master/detail
 * layout over the connector registry, and the Add Connector wizard. Each
 * registry endpoint loads independently — a failing side registry degrades its
 * own section instead of blanking the page.
 */

function countOrPlaceholder(count: number | undefined): string | number {
  return count ?? strings.connectors.metrics.unavailable;
}

function buildMetrics(
  registries: ConnectorRegistries,
  entries: ConnectorListEntry[],
): Metric[] {
  const copy = strings.connectors.metrics;
  const invariantCount = registries.evidenceInvariants.data?.invariants.length;

  return [
    {
      label: copy.connectors.label,
      // Reference connectors plus persisted-manifest-only connectors,
      // deduped by connector_id (the merged list length).
      value: countOrPlaceholder(registries.registry.data ? entries.length : undefined),
      detail: copy.connectors.detail,
    },
    {
      label: copy.runs.label,
      value: countOrPlaceholder(registries.runs.data?.runs.length),
      detail: copy.runs.detail,
    },
    {
      label: copy.pendingProposals.label,
      value: countOrPlaceholder(
        registries.ontologyProposals.data
          ? pendingProposalCount(registries.ontologyProposals.data.proposals)
          : undefined,
      ),
      detail: copy.pendingProposals.detail,
    },
    {
      label: copy.egressPolicies.label,
      value: countOrPlaceholder(registries.egressPolicies.data?.policies.length),
      detail: copy.egressPolicies.detail,
    },
    {
      label: copy.evidenceIssues.label,
      value: countOrPlaceholder(invariantCount),
      detail: copy.evidenceIssues.detail,
      ...(invariantCount !== undefined
        ? { tone: invariantCount > 0 ? ("action" as const) : ("ready" as const) }
        : {}),
    },
  ];
}

function formatUpdatedAt(updatedAt: Date): string {
  return new Intl.DateTimeFormat("en", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  }).format(updatedAt);
}

export function ConnectorConsole() {
  const registries = useConnectorRegistries();
  const { registry } = registries;
  const { triggerRefresh } = useConsole();
  const [requestedConnectorId] = useState<string | null>(() =>
    typeof window === "undefined"
      ? null
      : new URLSearchParams(window.location.search).get("connector_id"),
  );
  const [selectedConnectorId, setSelectedConnectorId] = useState("");
  const [wizardOpen, setWizardOpen] = useState(false);
  // Real fetch time (no hardcoded timestamps): stamped when a new registry
  // payload arrives, using the render-time state-adjustment pattern.
  const [fetchStamp, setFetchStamp] = useState<{ payload: unknown; at: Date } | null>(null);
  if (registry.data && fetchStamp?.payload !== registry.data) {
    setFetchStamp({ payload: registry.data, at: new Date() });
  }
  const updatedAt = fetchStamp?.at ?? null;

  const connectors = useMemo(() => registry.data?.connectors ?? [], [registry.data]);
  // Merge persisted manifests into the list so wizard registrations appear
  // immediately, deduped against the reference registry by connector_id.
  const entries = useMemo(
    () => mergeConnectorListEntries(connectors, registries.manifests.data?.manifests ?? []),
    [connectors, registries.manifests.data],
  );
  const selectedEntry = useMemo(
    () =>
      entries.find(
        (entry) =>
          entry.connector.manifest.connector_id
          === (selectedConnectorId || requestedConnectorId),
      ) ?? entries[0],
    [entries, selectedConnectorId, requestedConnectorId],
  );

  if (!registry.data) {
    if (registry.source === "loading") {
      return (
        <div aria-label="Loading connector API" className="grid gap-4">
          <LoadingPanel layout="metrics" rows={5} />
          <MasterDetail detail={<LoadingPanel layout="detail" />} list={<LoadingPanel rows={4} />} />
        </div>
      );
    }

    return (
      <ErrorPanel
        detail={strings.connectors.error.detail}
        endpoint={CONNECTOR_ENDPOINTS.registry}
        title={strings.connectors.error.title}
      />
    );
  }

  const registryData = registry.data;
  const wizard = (
    <AddConnectorWizard
      connectors={connectors}
      open={wizardOpen}
      onCreated={triggerRefresh}
      onOpenChange={setWizardOpen}
    />
  );

  return (
    <div className="grid gap-4">
      <div
        aria-label="Connector source and status"
        className="flex min-w-0 flex-wrap items-center justify-between gap-x-4 gap-y-2"
      >
        <p className="m-0 min-w-0 text-sm break-words text-muted">
          {registryData.plant_name} / {registryData.scenario} / {registryData.tenant_id}
        </p>
        <div className="flex min-w-0 flex-wrap items-center gap-2.5">
          <span className={`status-pill ${platformStatusClass(registryData.registry_status)}`}>
            <Cable size={15} />
            {platformStatusLabel(registryData.registry_status)}
          </span>
          {updatedAt ? (
            <span className="font-mono text-xs text-muted">
              {strings.connectors.header.updated} {formatUpdatedAt(updatedAt)}
            </span>
          ) : null}
          <Button
            className="px-4 py-2 text-sm"
            onClick={() => setWizardOpen(true)}
          >
            <Plus aria-hidden="true" size={15} />
            {strings.connectors.header.addConnector}
          </Button>
        </div>
      </div>

      <MetricStrip metrics={buildMetrics(registries, entries)} />

      {entries.length === 0 || !selectedEntry ? (
        <EmptyPanel
          action={{
            label: strings.connectors.empty.action,
            onClick: () => setWizardOpen(true),
          }}
          detail={strings.connectors.empty.detail}
          icon={Cable}
          title={strings.connectors.empty.title}
        />
      ) : (
        <MasterDetail
          detail={<ConnectorDetail entry={selectedEntry} registries={registries} />}
          list={
            <ConnectorList
              entries={entries}
              selectedConnectorId={selectedEntry.connector.manifest.connector_id}
              onSelect={setSelectedConnectorId}
            />
          }
        />
      )}

      {wizard}
    </div>
  );
}
