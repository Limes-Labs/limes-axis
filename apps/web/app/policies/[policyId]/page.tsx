import type { Metadata } from "next";

import { getServerStrings } from "@/lib/locale-server";
import { ConsolePage } from "@/components/console-page";
import { PolicyDetail } from "@/components/policy-detail";

type PolicyDetailPageProps = {
  params: Promise<{
    policyId: string;
  }>;
};

export async function generateMetadata({ params }: PolicyDetailPageProps): Promise<Metadata> {
  const [{ policyId }, strings] = await Promise.all([params, getServerStrings()]);
  return { title: strings.ui.detailPages.policyMetaTitle(policyId) };
}

export default async function PolicyDetailPage({ params }: PolicyDetailPageProps) {
  const strings = await getServerStrings();
  const { policyId } = await params;

  return (
    <ConsolePage
      pageKey="policies"
      subtitle={strings.clarity.policyPurpose}
      title={strings.ui.detailPages.policyTitle}
    >
      <PolicyDetail key={policyId} policyId={policyId} />
    </ConsolePage>
  );
}
