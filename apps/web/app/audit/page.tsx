import { PageActions } from "@/components/page-actions";
import { auditEvents } from "@/lib/foundation";

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

      <section className="table-panel">
        <table className="data-table">
          <thead>
            <tr>
              <th>Event</th>
              <th>Actor</th>
              <th>Scope</th>
              <th>Result</th>
            </tr>
          </thead>
          <tbody>
            {auditEvents.map((event) => (
              <tr key={`${event.event}-${event.scope}`}>
                <td className="mono">{event.event}</td>
                <td>{event.actor}</td>
                <td>{event.scope}</td>
                <td>{event.result}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </section>
  );
}
