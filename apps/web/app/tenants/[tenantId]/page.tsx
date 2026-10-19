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
  const [{ tenantId }, strings] = await Promise.all([params, getServerStrings()]);
  return { title: strings.ui.detailPages.tenantMetaTitle(tenantId) };
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
