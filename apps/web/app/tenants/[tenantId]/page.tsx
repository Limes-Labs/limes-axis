import type { Metadata } from "next";

import { getServerStrings } from "@/lib/locale-server";
import { ConsolePage } from "@/components/console-page";
import { TenantDetail } from "@/components/tenant-detail";

type TenantDetailPageProps = {
  params: Promise<{
    tenantId: string;
  }>;
};

// The raw tenant id stays out of the document title; the page shows the
// tenant's display name once the API record loads.
export async function generateMetadata(): Promise<Metadata> {
  const strings = await getServerStrings();
  return { title: strings.identifiers.tenantDetailTitle };
}

export default async function TenantDetailPage({ params }: TenantDetailPageProps) {
  const strings = await getServerStrings();
  const { tenantId } = await params;

  return (
    <ConsolePage
      pageKey="tenants"
      subtitle={strings.clarity.tenantPurpose}
      title={strings.ui.detailPages.tenantTitle}
    >
      <TenantDetail key={tenantId} tenantId={tenantId} />
    </ConsolePage>
  );
}
