import type { Metadata } from "next";

import { ConsolePage } from "@/components/console-page";
import { SimulationConsole } from "@/components/simulation-console";
import { getServerStrings } from "@/lib/locale-server";

export async function generateMetadata(): Promise<Metadata> {
  const strings = await getServerStrings();
  return {
    title: strings.pages.simulation.title,
    description: strings.pages.simulation.description,
  };
}

export default function SimulationPage() {
  return (
    <ConsolePage pageKey="simulation">
      <SimulationConsole />
    </ConsolePage>
  );
}
