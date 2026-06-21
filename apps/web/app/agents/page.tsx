import { PageActions } from "@/components/page-actions";
import { autonomyLevels } from "@/lib/foundation";

export default function AgentsPage() {
  return (
    <section className="page">
      <header className="page-header">
        <div>
          <p className="eyebrow">Agents</p>
          <h1 className="page-title">Autonomy and action registry</h1>
          <p className="page-copy">
            Agent behavior is bounded through autonomy levels, typed action schemas, permission
            checks, approval gates and model egress policy.
          </p>
        </div>
        <PageActions />
      </header>

      <section className="table-panel">
        <table className="data-table">
          <thead>
            <tr>
              <th>Level</th>
              <th>Mode</th>
              <th>Approval Boundary</th>
            </tr>
          </thead>
          <tbody>
            {autonomyLevels.map((level) => (
              <tr key={level.level}>
                <td className="mono">{level.level}</td>
                <td>
                  <strong>{level.label}</strong>
                </td>
                <td>{level.approval}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </section>
  );
}
