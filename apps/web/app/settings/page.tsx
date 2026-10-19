import type { Metadata } from "next";

import { PlatformSettingsConsole } from "@/components/platform-settings-console";
import { getServerStrings } from "@/lib/locale-server";

export async function generateMetadata(): Promise<Metadata> {
  const strings = await getServerStrings();
  return {
    title: strings.pages.settings.title,
    description: strings.pages.settings.description,
  };
}

export default function SettingsPage() {
  return <PlatformSettingsConsole />;
}
