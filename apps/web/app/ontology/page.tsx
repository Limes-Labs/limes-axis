import { PageActions } from "@/components/page-actions";
import { OntologyExplorer } from "@/components/ontology-explorer";

export default function OntologyPage() {
  return (
    <section className="page">
      <header className="page-header">
        <div>
          <p className="eyebrow">Ontology</p>
          <h1 className="page-title">Operational knowledge model</h1>
          <p className="page-copy">
            The read-only explorer maps the manufacturing reference demo into typed nodes,
            source-system links, permission scopes and operational relationships.
          </p>
        </div>
        <PageActions />
      </header>

      <OntologyExplorer />
    </section>
  );
}
