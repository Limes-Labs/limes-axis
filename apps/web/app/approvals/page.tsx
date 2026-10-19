import type { Metadata } from "next";

import { ConsolePage } from "@/components/console-page";
import { ApprovalInbox } from "@/components/approval-inbox";
import { getServerStrings } from "@/lib/locale-server";

export async function generateMetadata(): Promise<Metadata> {
  const strings = await getServerStrings();
  return {
    title: strings.pages.approvals.title,
    description: strings.pages.approvals.description,
  };
}

export default function ApprovalsPage() {
  return (
    <ConsolePage pageKey="approvals">
      <ApprovalInbox />
    </ConsolePage>
  );
}
