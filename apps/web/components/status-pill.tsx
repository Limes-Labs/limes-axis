import { statusLabel, type FoundationStatus } from "@/lib/foundation";

export function StatusPill({ status }: { status: FoundationStatus }) {
  return <span className={`status-pill status-${status}`}>{statusLabel(status)}</span>;
}
