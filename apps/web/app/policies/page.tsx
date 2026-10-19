import type { Metadata } from "next";

import { ConsolePage } from "@/components/console-page";
import { PolicyRegistry } from "@/components/policy-registry";
import { getServerStrings } from "@/lib/locale-server";

export async function generateMetadata(): Promise<Metadata> {
  const strings = await getServerStrings();
  return {
    title: strings.pages.policies.title,
    description: strings.pages.policies.description,
  };
}

export default function PoliciesPage() {
  return (
    <ConsolePage pageKey="policies">
      <PolicyRegistry />
    </ConsolePage>
  );
}
