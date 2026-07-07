import { ConsolePage } from "@/components/console-page";
import { TenantRegistry } from "@/components/tenant-registry";

export default function TenantsPage() {
  return (
    <ConsolePage
      eyebrow="Tenants"
      subtitle="Platform-operator tenant lifecycle and per-tenant quotas: provision, suspend, reactivate and administer tenants across the fleet with audited transitions."
      title="Tenant operations"
    >
      <TenantRegistry />
    </ConsolePage>
  );
}
