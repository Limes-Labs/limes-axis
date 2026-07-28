import type { Metadata } from "next";

import { ConsolePage } from "@/components/console-page";
import { OntologyEntityDetail } from "@/components/ontology-entity-detail";
import { decodeOntologyEntityRouteParam } from "@/lib/ontology-routes";

type OntologyEntityPageProps = {
  params: Promise<{
    nodeId: string;
  }>;
};

export async function generateMetadata({ params }: OntologyEntityPageProps): Promise<Metadata> {
  const { nodeId: routeNodeId } = await params;
  const nodeId = decodeOntologyEntityRouteParam(routeNodeId);
  return { title: `Entity ${nodeId}` };
}

export default async function OntologyEntityPage({ params }: OntologyEntityPageProps) {
  const { nodeId: routeNodeId } = await params;
  const nodeId = decodeOntologyEntityRouteParam(routeNodeId);

  return (
    <ConsolePage
      pageKey="ontology"
      subtitle="Connected relationships, permission scopes, evidence references and read-only governance boundaries."
      title="Entity detail"
    >
      <OntologyEntityDetail nodeId={nodeId} />
    </ConsolePage>
  );
}
