import { PageActions } from "@/components/page-actions";
import { ConnectorConsole } from "@/components/connector-console";

export default function ConnectorsPage() {
  return (
    <div className="stack">
      <header className="page-header">
        <div>
          <p className="eyebrow">Connectors</p>
          <h1 className="page-title">Connector intake</h1>
          <p className="page-copy">
            Connector manifests define source boundaries, schema mappings, credentials and sync
            posture before any data leaves a tenant-controlled runtime.
          </p>
        </div>
        <PageActions />
      </header>

      <ConnectorConsole />
    </div>
  );
}
