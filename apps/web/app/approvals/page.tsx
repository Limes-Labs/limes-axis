import { ApprovalInbox } from "@/components/approval-inbox";
import { PageActions } from "@/components/page-actions";

export default function ApprovalsPage() {
  return (
    <section className="page">
      <header className="page-header">
        <div>
          <p className="eyebrow">Approvals</p>
          <h1 className="page-title">Policy gate queue</h1>
          <p className="page-copy">
            Approval surfaces route high-risk agent proposals, external egress exceptions and
            workflow decisions through explicit human review and audit evidence.
          </p>
        </div>
        <PageActions />
      </header>

      <ApprovalInbox />
    </section>
  );
}
