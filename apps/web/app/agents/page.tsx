import { ActionRegistry } from "@/components/action-registry";
import { AgentRegistry } from "@/components/agent-registry";
import { PageActions } from "@/components/page-actions";

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

      <AgentRegistry />
      <ActionRegistry />
    </section>
  );
}
