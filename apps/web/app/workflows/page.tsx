import type { Metadata } from "next";

import { ConsolePage } from "@/components/console-page";
import { WorkflowConsole } from "@/components/workflow-console";
import { getServerStrings } from "@/lib/locale-server";

export async function generateMetadata(): Promise<Metadata> {
  const strings = await getServerStrings();
  return {
    title: strings.pages.workflows.title,
    description: strings.pages.workflows.description,
  };
}

export default function WorkflowsPage() {
  return (
    <ConsolePage pageKey="workflows">
      <WorkflowConsole />
    </ConsolePage>
  );
}
