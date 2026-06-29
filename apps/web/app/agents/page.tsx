import { ConsolePage } from "@/components/console-page";
import { ActionRegistry } from "@/components/action-registry";
import { AgentRegistry } from "@/components/agent-registry";

export default function AgentsPage() {
  return (
    <ConsolePage
      eyebrow="Agents"
      subtitle="Autonomy levels, typed action schemas, permission checks, approval gates and model egress policy."
      title="Autonomy and action registry"
    >
      <AgentRegistry />
      <ActionRegistry />
    </ConsolePage>
  );
}