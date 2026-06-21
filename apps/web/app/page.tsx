import { PageActions } from "@/components/page-actions";
import { PlatformOverview } from "@/components/platform-overview";

export default function OverviewPage() {
  return (
    <section className="page">
      <header className="page-header">
        <div>
          <p className="eyebrow">Platform</p>
          <h1 className="page-title">Operations control plane</h1>
          <p className="page-copy">
            The governance overview connects operational risk, workflow state, approval gates,
            governed agents and audit evidence for the manufacturing reference demo.
          </p>
        </div>
        <PageActions />
      </header>

      <PlatformOverview />
    </section>
  );
}
