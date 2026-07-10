import { ConsolePage } from "@/components/console-page";
import { WorkflowConsole } from "@/components/workflow-console";

export default function WorkflowsPage() {
  return (
    <ConsolePage pageKey="workflows">
      <WorkflowConsole />
    </ConsolePage>
  );
}
