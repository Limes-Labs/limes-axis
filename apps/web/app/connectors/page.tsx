import type { Metadata } from "next";

import { ConsolePage } from "@/components/console-page";
import { ConnectorConsole } from "@/components/connector-console";
import { getServerStrings } from "@/lib/locale-server";

export async function generateMetadata(): Promise<Metadata> {
  const strings = await getServerStrings();
  return {
    title: strings.pages.connectors.title,
    description: strings.pages.connectors.description,
  };
}

export default function ConnectorsPage() {
  return (
    <ConsolePage pageKey="connectors">
      <ConnectorConsole />
    </ConsolePage>
  );
}
