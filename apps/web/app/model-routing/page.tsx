import { ModelRoutingConsole } from "@/components/model-routing-console";
import { PageActions } from "@/components/page-actions";

export default function ModelRoutingPage() {
  return (
    <section className="page">
      <header className="page-header">
        <div>
          <p className="eyebrow">Models</p>
          <h1 className="page-title">Model routing and spend</h1>
          <p className="page-copy">
            Route selection, egress decisions, token estimates, cost posture and audit evidence
            stay visible before any governed agent can rely on a model path.
          </p>
        </div>
        <PageActions />
      </header>

      <ModelRoutingConsole />
    </section>
  );
}
