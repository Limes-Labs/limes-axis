import type { Metadata } from "next";

import { getServerStrings } from "@/lib/locale-server";
import { ConsolePage } from "@/components/console-page";
import { TenantDetail } from "@/components/tenant-detail";

type TenantDetailPageProps = {
  params: Promise<{
    tenantId: string;
  }>;
};

export async function generateMetadata({ params }: TenantDetailPageProps): Promise<Metadata> {
  const { tenantId } = await params;
  return { title: `Tenant ${tenantId}` };
}

export default async function TenantDetailPage({ params }: TenantDetailPageProps) {
  const strings = await getServerStrings();
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
