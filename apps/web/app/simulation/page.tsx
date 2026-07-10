import { ConsolePage } from "@/components/console-page";
import { SimulationConsole } from "@/components/simulation-console";

export default function SimulationPage() {
  return (
    <ConsolePage pageKey="simulation">
      <SimulationConsole />
    </ConsolePage>
  );
}
