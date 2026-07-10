import { ConsolePage } from "@/components/console-page";
import { ConnectorConsole } from "@/components/connector-console";

export default function ConnectorsPage() {
  return (
    <ConsolePage pageKey="connectors">
      <ConnectorConsole />
    </ConsolePage>
  );
}
