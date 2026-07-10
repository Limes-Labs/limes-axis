import { ConsolePage } from "@/components/console-page";
import { ApprovalInbox } from "@/components/approval-inbox";

export default function ApprovalsPage() {
  return (
    <ConsolePage pageKey="approvals">
      <ApprovalInbox />
    </ConsolePage>
  );
}
