import { ConsolePage } from "@/components/console-page";
import { OntologyExplorer } from "@/components/ontology-explorer";

export default function OntologyPage() {
  return (
    <ConsolePage pageKey="ontology">
      <OntologyExplorer />
    </ConsolePage>
  );
}
