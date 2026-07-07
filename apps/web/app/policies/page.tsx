import { ConsolePage } from "@/components/console-page";
import { PolicyRegistry } from "@/components/policy-registry";

export default function PoliciesPage() {
  return (
    <ConsolePage
      eyebrow="Policies"
      subtitle="Tenant-scoped platform policies with typed conditions, append-only revisions, console authoring and deterministic dry-run evaluation."
      title="Platform policy rules"
    >
      <PolicyRegistry />
    </ConsolePage>
  );
}
