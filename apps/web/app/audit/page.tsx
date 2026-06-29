import { ConsolePage } from "@/components/console-page";
import { AuditExplorer } from "@/components/audit-explorer";

export default function AuditPage() {
  return (
    <ConsolePage
      eyebrow="Audit"
      subtitle="Append-only operational evidence with retention windows, export bundles and integrity proofs."
      title="Append-only evidence"
    >
      <AuditExplorer />
    </ConsolePage>
  );
}