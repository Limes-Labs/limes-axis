import { ConsolePage } from "@/components/console-page";
import { PlatformOverview } from "@/components/platform-overview";

export default function OverviewPage() {
  return (
    <ConsolePage pageKey="overview">
      <PlatformOverview />
    </ConsolePage>
  );
}
