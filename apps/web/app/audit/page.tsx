import { ConsolePage } from "@/components/console-page";
import { AuditExplorer } from "@/components/audit-explorer";

export default function AuditPage() {
  return (
    <ConsolePage pageKey="audit">
      <AuditExplorer />
    </ConsolePage>
  );
}
