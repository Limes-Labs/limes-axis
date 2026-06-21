import { AuditExplorer } from "@/components/audit-explorer";
import { PageActions } from "@/components/page-actions";

export default function AuditPage() {
  return (
    <section className="page">
      <header className="page-header">
        <div>
          <p className="eyebrow">Audit</p>
          <h1 className="page-title">Append-only evidence</h1>
          <p className="page-copy">
            The audit ledger starts as a Postgres-backed append-only table and becomes the shared
            evidence contract for approvals, actions, workflows and tenant events.
          </p>
        </div>
        <PageActions />
      </header>

      <AuditExplorer />
    </section>
  );
}
