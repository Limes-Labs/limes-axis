import { ShieldCheck } from "lucide-react";

import { PageActions } from "@/components/page-actions";
import { StatusPill } from "@/components/status-pill";
import { auditEvents, foundationMetrics, workflowChecks } from "@/lib/foundation";

export default function OverviewPage() {
  return (
    <section className="page">
      <header className="page-header">
        <div>
          <p className="eyebrow">Platform Foundation</p>
          <h1 className="page-title">Operations control plane</h1>
          <p className="page-copy">
            Foundation surfaces the boundaries that must stay sovereign: runtime, tenancy,
            ontology, approvals, audit, model routing and future extraction points.
          </p>
        </div>
        <PageActions />
      </header>

      <div className="metric-grid">
        {foundationMetrics.map((metric) => (
          <article className="metric-card" key={metric.label}>
            <div className="row">
              <p className="metric-label">{metric.label}</p>
              <StatusPill status={metric.status} />
            </div>
            <p className="metric-value">{metric.value}</p>
            <p className="metric-detail">{metric.detail}</p>
          </article>
        ))}
      </div>

      <div className="two-column">
        <section className="panel">
          <p className="section-label">Runtime Checks</p>
          <h2 className="panel-title">Workflow foundation</h2>
          <div className="stack">
            {workflowChecks.map((item) => (
              <div className="row" key={item.label}>
                <div>
                  <p className="row-title">{item.label}</p>
                  <p className="row-detail">{item.runtime}</p>
                </div>
                <StatusPill status={item.status} />
              </div>
            ))}
          </div>
        </section>

        <section className="panel">
          <p className="section-label">Recent Evidence</p>
          <h2 className="panel-title">Audit trail</h2>
          <div className="stack">
            {auditEvents.map((item) => (
              <div className="row" key={`${item.event}-${item.scope}`}>
                <div>
                  <p className="row-title mono">{item.event}</p>
                  <p className="row-detail">
                    {item.actor} / {item.scope}
                  </p>
                </div>
                <ShieldCheck size={18} aria-label={item.result} />
              </div>
            ))}
          </div>
        </section>
      </div>
    </section>
  );
}
