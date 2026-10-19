import type { Metadata } from "next";

import { ConsolePage } from "@/components/console-page";
import { ActionRegistry } from "@/components/action-registry";
import { Disclosure } from "@/components/ui/disclosure";
import { AgentRegistry } from "@/components/agent-registry";
import { getServerStrings } from "@/lib/locale-server";

export async function generateMetadata(): Promise<Metadata> {
  const strings = await getServerStrings();
  return {
    title: strings.pages.agents.title,
    description: strings.pages.agents.description,
  };
}

export default async function AgentsPage() {
  const strings = await getServerStrings();
  return (
    <ConsolePage pageKey="agents">
      <AgentRegistry />
      <Disclosure title={strings.clarity.actionCatalog}>
        <ActionRegistry />
      </Disclosure>
    </ConsolePage>
  );
}
