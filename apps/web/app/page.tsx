import type { Metadata } from "next";

import { ConsolePage } from "@/components/console-page";
import { PlatformOverview } from "@/components/platform-overview";
import { getServerStrings } from "@/lib/locale-server";

export async function generateMetadata(): Promise<Metadata> {
  const strings = await getServerStrings();
  return {
    title: strings.pages.overview.title,
    description: strings.pages.overview.description,
  };
}

export default function OverviewPage() {
  return (
    <ConsolePage pageKey="overview">
      <PlatformOverview />
    </ConsolePage>
  );
}
