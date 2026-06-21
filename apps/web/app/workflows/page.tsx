import { PageActions } from "@/components/page-actions";
import { WorkflowConsole } from "@/components/workflow-console";

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

      <WorkflowConsole />
    </section>
  );
}
