import { ConsolePage } from "@/components/console-page";
import { ActionRegistry } from "@/components/action-registry";
import { AgentRegistry } from "@/components/agent-registry";

export default function AgentsPage() {
  return (
    <ConsolePage pageKey="agents">
      <AgentRegistry />
      <ActionRegistry />
    </ConsolePage>
  );
}
