"use client";

import { FileClock } from "lucide-react";

import { Card } from "@/components/ui/card";
import { DataTable } from "@/components/ui/data-table";
import { DetailGrid, KeyValueRow } from "@/components/ui/detail-grid";
import { Eyebrow } from "@/components/ui/eyebrow";
import { InspectDrawer } from "@/components/ui/inspect-drawer";
import { EmptyPanel } from "@/components/ui/states";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { formatConnectorLabel, type ConnectorRegistryItem } from "@/lib/connectors-demo";
import {
  manifestRecordForConnector,
  type ConnectorListEntry,
} from "@/lib/connectors-console";
import { strings } from "@/lib/strings";
import type { ConnectorRegistries } from "@/lib/use-connector-registries";

import { ConnectorGovernance } from "./governance";
import { ConnectorRuns } from "./runs";

/*
 * Connector detail pane: Overview / Data & Schema / Runs / Governance &
 * Evidence tabs. The old ~40 invariant tiles compress into the governance tab
 * as DetailGrid sections with Inspect drawers.
 */

function ChipList({ items, emptyLabel }: { items: string[]; emptyLabel?: string }) {
  if (items.length === 0) {
    return <span className="text-sm text-muted">{emptyLabel ?? "None"}</span>;
  }

  return (
    <div className="flex min-w-0 flex-wrap gap-2">
      {items.map((item) => (
        <span
          className="inline-flex max-w-full min-w-0 items-center rounded-full border border-line bg-surface px-3 py-1 font-mono text-xs break-words text-muted dark:border-white/15 dark:bg-transparent"
          key={item}
        >
          {item}
        </span>
      ))}
    </div>
  );
}

function OverviewTab({
  connector,
  registries,
}: {
  connector: ConnectorRegistryItem;
  registries: ConnectorRegistries;
}) {
  const copy = strings.connectors.overview;
  const { manifest, runtime_policy: runtimePolicy } = connector;
  const manifestRecord = registries.manifests.data
    ? manifestRecordForConnector(
        registries.manifests.data.manifests,
        manifest.connector_id,
      )
    : null;

  return (
    <div className="grid content-start gap-5">
      <DetailGrid>
        <KeyValueRow label={copy.type}>
          {formatConnectorLabel(manifest.connector_type)}
        </KeyValueRow>
        <KeyValueRow label={copy.version}>{manifest.version}</KeyValueRow>
        <KeyValueRow label={copy.source}>
          {formatConnectorLabel(manifest.source_type)}
        </KeyValueRow>
        <KeyValueRow label={copy.syncModes}>
          {manifest.sync_modes.map(formatConnectorLabel).join(", ")}
        </KeyValueRow>
        <KeyValueRow label={copy.boundary}>
          {formatConnectorLabel(manifest.runtime_boundary)}
        </KeyValueRow>
        <KeyValueRow label={copy.credentials}>
          {formatConnectorLabel(manifest.credential_requirements.storage)}
        </KeyValueRow>
        <KeyValueRow label={copy.payloadPolicy}>
          {formatConnectorLabel(runtimePolicy.payload_policy)}
        </KeyValueRow>
        <KeyValueRow label={copy.egressPolicy} mono>
          {runtimePolicy.egress_policy}
        </KeyValueRow>
      </DetailGrid>

      <div className="grid gap-3">
        <div className="grid gap-2">
          <Eyebrow>{copy.permissions}</Eyebrow>
          <ChipList items={manifest.required_permissions} />
        </div>
        <div className="grid gap-2">
          <Eyebrow>{copy.blocked}</Eyebrow>
          <ChipList items={runtimePolicy.blocked_operations} />
        </div>
      </div>

      <div className="grid gap-2 border-t border-line/60 pt-4 dark:border-white/10">
        <Eyebrow>{copy.manifest}</Eyebrow>
        {manifestRecord ? (
          <DetailGrid>
            <KeyValueRow label="Status">
              {formatConnectorLabel(manifestRecord.status)}
            </KeyValueRow>
            <KeyValueRow label={copy.manifestRegisteredBy}>
              {manifestRecord.registered_by}
            </KeyValueRow>
          </DetailGrid>
        ) : (
          <p className="m-0 text-sm text-muted">{copy.manifestMissing}</p>
        )}
      </div>
    </div>
  );
}

function DataSchemaTab({ connector }: { connector: ConnectorRegistryItem }) {
  const copy = strings.connectors.schema;
  const { schema_fields: schemaFields } = connector.manifest;
  const sample = connector.preview_sample;

  return (
    <div className="grid content-start gap-5">
      <section className="grid gap-2">
        <div className="grid gap-1">
          <Eyebrow>{copy.mappingTitle}</Eyebrow>
          <p className="m-0 text-sm text-muted">{copy.mappingDetail}</p>
        </div>
        <DataTable aria-label={copy.mappingTitle} minWidth={520}>
          <thead>
            <tr>
              <th>{copy.columns.source}</th>
              <th>{copy.columns.target}</th>
              <th>{copy.columns.ontology}</th>
              <th>{copy.columns.type}</th>
              <th>{copy.columns.required}</th>
            </tr>
          </thead>
          <tbody>
            {schemaFields.map((field) => (
              <tr key={field.source_column}>
                <td className="font-mono text-xs">{field.source_column}</td>
                <td className="font-mono text-xs">{field.target_field}</td>
                <td className="font-mono text-xs">{field.ontology_target}</td>
                <td className="text-xs text-muted">{field.data_type}</td>
                <td className="text-xs text-muted">
                  {field.required ? copy.requiredYes : copy.requiredNo}
                </td>
              </tr>
            ))}
          </tbody>
        </DataTable>
      </section>

      <section className="grid gap-2">
        <div className="grid gap-1">
          <Eyebrow>{copy.sampleTitle}</Eyebrow>
          <p className="m-0 text-sm text-muted">
            {copy.sampleDetail}{" "}
            <span className="font-mono text-xs">{sample.file_name}</span>
          </p>
        </div>
        {sample.sample_rows.length === 0 ? (
          <p className="m-0 text-sm text-muted">{copy.sampleEmpty}</p>
        ) : (
          <DataTable aria-label={copy.sampleTitle} minWidth={420}>
            <thead>
              <tr>
                {sample.headers.map((header) => (
                  <th key={header}>{header}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {sample.sample_rows.map((row, rowIndex) => (
                <tr key={rowIndex}>
                  {sample.headers.map((header) => (
                    <td className="text-xs" key={header}>
                      {row[header] ?? ""}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </DataTable>
        )}
      </section>
    </div>
  );
}

/** Placeholder for sync surfaces of a just-registered, not-yet-activated manifest. */
function PendingActivationPanel() {
  return (
    <EmptyPanel
      detail={strings.connectors.pendingActivation.detail}
      icon={FileClock}
      title={strings.connectors.pendingActivation.title}
    />
  );
}

export function ConnectorDetail({
  entry,
  registries,
}: {
  entry: ConnectorListEntry;
  registries: ConnectorRegistries;
}) {
  const tabs = strings.connectors.tabs;
  const { connector } = entry;
  const { manifest } = connector;
  // Manifest-only entries (wizard registrations the reference registry does
  // not know yet) cannot preview or run syncs, so those tabs explain the
  // pending activation instead of offering actions that would 404/422.
  const activationPending = entry.source === "manifest";

  return (
    <Card className="grid content-start gap-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="grid max-w-xl gap-1">
          <Eyebrow>{formatConnectorLabel(manifest.connector_type)}</Eyebrow>
          <h2 className="font-display m-0 text-xl text-ink">{manifest.display_name}</h2>
          <p className="m-0 font-mono text-xs break-words text-muted">
            {manifest.connector_id}
          </p>
        </div>
        <InspectDrawer record={connector} title={manifest.display_name} />
      </div>

      <Tabs defaultValue="overview">
        <TabsList>
          <TabsTrigger value="overview">{tabs.overview}</TabsTrigger>
          <TabsTrigger value="schema">{tabs.dataSchema}</TabsTrigger>
          <TabsTrigger value="runs">{tabs.runs}</TabsTrigger>
          <TabsTrigger value="governance">{tabs.governance}</TabsTrigger>
        </TabsList>
        <TabsContent value="overview">
          <OverviewTab connector={connector} registries={registries} />
        </TabsContent>
        <TabsContent value="schema">
          {activationPending ? <PendingActivationPanel /> : <DataSchemaTab connector={connector} />}
        </TabsContent>
        <TabsContent value="runs">
          {activationPending ? (
            <PendingActivationPanel />
          ) : (
            <ConnectorRuns connector={connector} registries={registries} />
          )}
        </TabsContent>
        <TabsContent value="governance">
          <ConnectorGovernance connectorId={manifest.connector_id} registries={registries} />
        </TabsContent>
      </Tabs>
    </Card>
  );
}
