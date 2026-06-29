import { ConsolePage } from "@/components/console-page";
import { ApprovalInbox } from "@/components/approval-inbox";

export default function ApprovalsPage() {
  return (
    <ConsolePage
      eyebrow="Approvals"
      subtitle="High-risk agent proposals, external egress exceptions and workflow decisions through explicit human review."
      title="Policy gate queue"
    >
      <ApprovalInbox />
    </ConsolePage>
  );
}