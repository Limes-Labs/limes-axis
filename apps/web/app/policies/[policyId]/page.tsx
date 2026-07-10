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
      pageKey="policies"
      subtitle="Full policy definition, typed conditions, revision authoring with idempotent replay, revision compare and dry-run evaluation."
      title="Policy detail"
    >
      <PolicyDetail key={policyId} policyId={policyId} />
    </ConsolePage>
  );
}
