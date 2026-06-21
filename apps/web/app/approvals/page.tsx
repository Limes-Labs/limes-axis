import { CheckCircle2, CirclePause, ShieldAlert } from "lucide-react";

import { PageActions } from "@/components/page-actions";

const approvalRows = [
  {
    label: "Model egress exception",
    owner: "Security policy",
    icon: ShieldAlert,
    status: "Blocked",
  },
  {
    label: "High-risk operation",
    owner: "Human approval",
    icon: CirclePause,
    status: "Waiting",
  },
  {
    label: "Local workflow signal",
    owner: "Runtime adapter",
    icon: CheckCircle2,
    status: "Recorded",
  },
];

export default function ApprovalsPage() {
  return (
    <section className="page">
      <header className="page-header">
        <div>
          <p className="eyebrow">Approvals</p>
          <h1 className="page-title">Policy gate queue</h1>
          <p className="page-copy">
            Approval surfaces are designed for high-risk actions, external egress exceptions and
            workflow decisions that need durable evidence.
          </p>
        </div>
        <PageActions />
      </header>

      <section className="panel">
        <p className="section-label">Queue</p>
        <h2 className="panel-title">Foundation gates</h2>
        <div className="stack">
          {approvalRows.map((row) => {
            const Icon = row.icon;

            return (
              <div className="row" key={row.label}>
                <div>
                  <p className="row-title">{row.label}</p>
                  <p className="row-detail">{row.owner}</p>
                </div>
                <span className="command-button">
                  <Icon size={17} />
                  {row.status}
                </span>
              </div>
            );
          })}
        </div>
      </section>
    </section>
  );
}
