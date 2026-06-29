import { ConsolePage } from "@/components/console-page";
import { WorkflowConsole } from "@/components/workflow-console";

export default function WorkflowsPage() {
  return (
    <ConsolePage
      eyebrow="Workflows"
      subtitle="Durable orchestration instances, approval signals and runtime adapter evidence from persisted workflow runs."
      title="Runtime adapter track"
    >
      <WorkflowConsole />
    </ConsolePage>
  );
}