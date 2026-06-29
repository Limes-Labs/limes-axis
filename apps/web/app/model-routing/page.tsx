import { ConsolePage } from "@/components/console-page";
import { ModelRoutingConsole } from "@/components/model-routing-console";

export default function ModelRoutingPage() {
  return (
    <ConsolePage
      eyebrow="Models"
      subtitle="Provider-agnostic routing posture, egress policy and cost observability from persisted telemetry."
      title="Model routing and spend"
    >
      <ModelRoutingConsole />
    </ConsolePage>
  );
}