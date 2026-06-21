import { PageActions } from "@/components/page-actions";
import { StatusPill } from "@/components/status-pill";
import { workflowChecks } from "@/lib/foundation";

export default function WorkflowsPage() {
  return (
    <section className="page">
      <header className="page-header">
        <div>
          <p className="eyebrow">Workflows</p>
          <h1 className="page-title">Runtime adapter track</h1>
          <p className="page-copy">
            Temporal stays behind an Axis runtime port, keeping orchestration replaceable while
            preserving workflow state, approval signals and audit evidence.
          </p>
        </div>
        <PageActions />
      </header>

      <section className="panel">
        <p className="section-label">Runtime</p>
        <h2 className="panel-title">Foundation sequence</h2>
        <div className="timeline">
          {workflowChecks.map((check, index) => (
            <div className="timeline-item" key={check.label}>
              <div className="timeline-index">{index + 1}</div>
              <div className="row">
                <div>
                  <p className="row-title">{check.label}</p>
                  <p className="row-detail">{check.runtime}</p>
                </div>
                <StatusPill status={check.status} />
              </div>
            </div>
          ))}
        </div>
      </section>
    </section>
  );
}
