import { ConsolePage } from "@/components/console-page";
import { ConnectorConsole } from "@/components/connector-console";

export default function ConnectorsPage() {
  return (
    <ConsolePage
      eyebrow="Connectors"
      subtitle="Manifests, credentials, sync checkpoints, promotion policies and evidence snapshots from the Axis API."
      title="Connector intake"
    >
      <ConnectorConsole />
    </ConsolePage>
  );
}