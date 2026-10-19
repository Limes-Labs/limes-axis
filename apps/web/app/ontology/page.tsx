import type { Metadata } from "next";

import { ConsolePage } from "@/components/console-page";
import { OntologyExplorer } from "@/components/ontology-explorer";
import { getServerStrings } from "@/lib/locale-server";

export async function generateMetadata(): Promise<Metadata> {
  const strings = await getServerStrings();
  return {
    title: strings.pages.ontology.title,
    description: strings.pages.ontology.description,
  };
}

export default function OntologyPage() {
  return (
    <ConsolePage pageKey="ontology">
      <OntologyExplorer />
    </ConsolePage>
  );
}
