import { ConsolePage } from "@/components/console-page";
import { SimulationConsole } from "@/components/simulation-console";

export default function SimulationPage() {
  return (
    <ConsolePage
      eyebrow="Simulation"
      subtitle="Baseline versus simulated policy decisions and governed connector diffs over historical workflow evidence."
      title="Replay and simulation"
    >
      <SimulationConsole />
    </ConsolePage>
  );
}