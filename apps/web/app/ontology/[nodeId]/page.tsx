import { OntologyEntityDetail } from "@/components/ontology-entity-detail";
import { PageActions } from "@/components/page-actions";

type OntologyEntityPageProps = {
  params: Promise<{
    nodeId: string;
  }>;
};

export default async function OntologyEntityPage({ params }: OntologyEntityPageProps) {
  const { nodeId } = await params;

  return (
    <section className="page">
      <header className="page-header">
        <div>
          <p className="eyebrow">Ontology</p>
          <h1 className="page-title">Entity detail</h1>
          <p className="page-copy">
            Inspect a public-safe ontology node, its connected relationships, permission scopes,
            evidence references and read-only governance boundaries.
          </p>
        </div>
        <PageActions />
      </header>

      <OntologyEntityDetail nodeId={nodeId} />
    </section>
  );
}
