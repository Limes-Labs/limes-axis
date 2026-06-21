import { PageActions } from "@/components/page-actions";
import { StatusPill } from "@/components/status-pill";
import { ontologyPrimitives } from "@/lib/foundation";

export default function OntologyPage() {
  return (
    <section className="page">
      <header className="page-header">
        <div>
          <p className="eyebrow">Ontology</p>
          <h1 className="page-title">Operational knowledge model</h1>
          <p className="page-copy">
            The foundation ontology starts with typed primitives that can map operations,
            approvals, evidence and system boundaries without coupling the product to one domain.
          </p>
        </div>
        <PageActions />
      </header>

      <section className="table-panel">
        <table className="data-table">
          <thead>
            <tr>
              <th>Primitive</th>
              <th>Role</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {ontologyPrimitives.map((primitive) => (
              <tr key={primitive.label}>
                <td>
                  <strong>{primitive.label}</strong>
                </td>
                <td>{primitive.role}</td>
                <td>
                  <StatusPill status={primitive.status} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </section>
  );
}
