import { ConsolePage } from "@/components/console-page";
import { PolicyRegistry } from "@/components/policy-registry";

export default function PoliciesPage() {
  return (
    <ConsolePage pageKey="policies">
      <PolicyRegistry />
    </ConsolePage>
  );
}
