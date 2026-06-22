import { PageActions } from "@/components/page-actions";
import { SimulationConsole } from "@/components/simulation-console";

export default function SimulationPage() {
  return (
    <div className="page">
      <header className="page-header">
        <div>
          <p className="eyebrow">Simulation</p>
          <h1 className="page-title">Replay and simulation</h1>
          <p className="page-copy">
            Replay artifacts combine workflow timeline history, audit evidence and deterministic
            policy previews so governance teams can inspect what stays blocked before any production
            mutation path is enabled.
          </p>
        </div>
        <PageActions />
      </header>

      <SimulationConsole />
    </div>
  );
}
