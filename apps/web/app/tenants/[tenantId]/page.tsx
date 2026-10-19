import type { Metadata } from "next";

import { strings } from "@/lib/strings";
import { ConsolePage } from "@/components/console-page";
import { TenantDetail } from "@/components/tenant-detail";

type TenantDetailPageProps = {
  params: Promise<{
    tenantId: string;
  }>;
};

// The raw tenant id stays out of the document title; the page shows the
// tenant's display name once the API record loads.
export const metadata: Metadata = { title: strings.identifiers.tenantDetailTitle };

export default async function TenantDetailPage({ params }: TenantDetailPageProps) {
  const { tenantId } = await params;

  return (
    <ConsolePage
      pageKey="tenants"
      subtitle={strings.clarity.tenantPurpose}
      title="Tenant detail"
    >
      <TenantDetail key={tenantId} tenantId={tenantId} />
    </ConsolePage>
  );
}
