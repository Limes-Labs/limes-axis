import { ConsolePage } from "@/components/console-page";
import { TenantRegistry } from "@/components/tenant-registry";

export default function TenantsPage() {
  return (
    <ConsolePage pageKey="tenants">
      <TenantRegistry />
    </ConsolePage>
  );
}
