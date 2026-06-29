import { ConsolePage } from "@/components/console-page";
import { OntologyExplorer } from "@/components/ontology-explorer";

export default function OntologyPage() {
  return (
    <ConsolePage
      eyebrow="Ontology"
      subtitle="Typed nodes, source-system links, permission scopes and operational relationships from the Axis API."
      title="Operational knowledge model"
    >
      <OntologyExplorer />
    </ConsolePage>
  );
}