import type { Metadata } from "next";

import { ConsolePage } from "@/components/console-page";
import { AuditExplorer } from "@/components/audit-explorer";
import { getServerStrings } from "@/lib/locale-server";

export async function generateMetadata(): Promise<Metadata> {
  const strings = await getServerStrings();
  return {
    title: strings.pages.audit.title,
    description: strings.pages.audit.description,
  };
}

export default function AuditPage() {
  return (
    <ConsolePage pageKey="audit">
      <AuditExplorer />
    </ConsolePage>
  );
}
