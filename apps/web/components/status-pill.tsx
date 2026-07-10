import { statusLabel, type FoundationStatus } from "@/lib/foundation";
import {
  platformStatusClass,
  platformStatusLabel,
  type PlatformStatus,
} from "@/lib/platform-overview";

export function StatusPill({ status }: { status: FoundationStatus }) {
  return <span className={`status-pill status-${status}`}>{statusLabel(status)}</span>;
}

/** Pill for the API's ready / watch / action_required platform statuses. */
export function PlatformStatusPill({ status }: { status: PlatformStatus }) {
  return (
    <span className={`status-pill ${platformStatusClass(status)}`}>
      {platformStatusLabel(status)}
    </span>
  );
}
