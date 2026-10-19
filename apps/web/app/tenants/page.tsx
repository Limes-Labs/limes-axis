import type { Metadata } from "next";

import { ConsolePage } from "@/components/console-page";
import { TenantRegistry } from "@/components/tenant-registry";
import { getServerStrings } from "@/lib/locale-server";

export async function generateMetadata(): Promise<Metadata> {
  const strings = await getServerStrings();
  return {
    title: strings.pages.tenants.title,
    description: strings.pages.tenants.description,
  };
}

export default function TenantsPage() {
  return (
    <ConsolePage pageKey="tenants">
      <TenantRegistry />
    </ConsolePage>
  );
}
