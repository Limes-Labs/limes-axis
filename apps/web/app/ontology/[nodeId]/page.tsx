import type { Metadata } from "next";

import { getServerStrings } from "@/lib/locale-server";
import { ConsolePage } from "@/components/console-page";
import { OntologyEntityDetail } from "@/components/ontology-entity-detail";

type OntologyEntityPageProps = {
  params: Promise<{
    nodeId: string;
  }>;
};

export async function generateMetadata({ params }: OntologyEntityPageProps): Promise<Metadata> {
  const [{ nodeId }, strings] = await Promise.all([params, getServerStrings()]);
  return { title: strings.ui.detailPages.entityMetaTitle(nodeId) };
}

export default async function OntologyEntityPage({ params }: OntologyEntityPageProps) {
  const strings = await getServerStrings();
  const { nodeId } = await params;

  return (
    <ConsolePage
      pageKey="ontology"
      subtitle={strings.clarity.entityPurpose}
      title={strings.ui.detailPages.entityTitle}
    >
      <OntologyEntityDetail nodeId={nodeId} />
    </ConsolePage>
  );
}
