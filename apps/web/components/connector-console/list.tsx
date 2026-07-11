"use client";

import { Card } from "@/components/ui/card";
import { Eyebrow } from "@/components/ui/eyebrow";
import { PlatformStatusPill } from "@/components/status-pill";
import { cn } from "@/lib/cn";
import type { ConnectorListEntry } from "@/lib/connectors-console";
import { formatConnectorLabel } from "@/lib/connectors-demo";
import { strings } from "@/lib/strings";

/**
 * Connector list rail: reference connectors plus persisted manifest records
 * merged in (so a wizard registration appears immediately). Manifest-only
 * entries carry a "Registered" pill instead of a runtime status.
 */
export function ConnectorList({
  entries,
  selectedConnectorId,
  onSelect,
}: {
  entries: ConnectorListEntry[];
  selectedConnectorId: string;
  onSelect: (connectorId: string) => void;
}) {
  return (
    <Card className="grid content-start gap-4">
      <div className="grid gap-1">
        <Eyebrow>{strings.connectors.list.eyebrow}</Eyebrow>
        <h2 className="font-display m-0 text-xl text-ink">
          {entries.length} {entries.length === 1 ? "connector" : "connectors"}
        </h2>
      </div>
      <div className="grid gap-2">
        {entries.map((entry) => {
          const { connector } = entry;
          const isSelected = connector.manifest.connector_id === selectedConnectorId;

          return (
            <button
              aria-pressed={isSelected}
              className={cn(
                "flex w-full cursor-pointer items-start justify-between gap-3 rounded-2xl border px-4 py-3 text-left transition-colors",
                isSelected
                  ? "border-signal/60 bg-tint-100 dark:bg-signal/15"
                  : "border-line bg-transparent hover:border-signal/40 hover:bg-tint-50 dark:border-white/10 dark:hover:bg-white/5",
              )}
              key={connector.manifest.connector_id}
              onClick={() => onSelect(connector.manifest.connector_id)}
              type="button"
            >
              <span className="grid min-w-0 gap-0.5">
                <span className="text-sm font-medium text-ink">
                  {connector.manifest.display_name}
                </span>
                <span className="text-xs text-muted">
                  {formatConnectorLabel(connector.manifest.connector_type)}
                </span>
                <span className="text-xs text-muted">
                  {connector.preview_sample.record_count} sample rows
                </span>
              </span>
              {entry.source === "manifest" ? (
                <span className="status-pill status-checking">
                  {strings.connectors.list.registeredPill}
                </span>
              ) : (
                <PlatformStatusPill status={connector.connector_status} />
              )}
            </button>
          );
        })}
      </div>
    </Card>
  );
}
