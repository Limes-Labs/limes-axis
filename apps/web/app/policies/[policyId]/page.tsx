import { ConsolePage } from "@/components/console-page";
import { PolicyDetail } from "@/components/policy-detail";

type PolicyDetailPageProps = {
  params: Promise<{
    policyId: string;
  }>;
};

export default async function PolicyDetailPage({ params }: PolicyDetailPageProps) {
  const { policyId } = await params;

  return (
    <ConsolePage
      eyebrow="Policies"
      subtitle="Full policy definition, typed conditions, append-only revision history and dry-run evaluation."
      title="Policy detail"
    >
      <PolicyDetail policyId={policyId} />
    </ConsolePage>
  );
}
