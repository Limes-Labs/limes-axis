import type { Metadata } from "next";

import { ConsolePage } from "@/components/console-page";
import { DataCatalog } from "@/components/data-catalog";
import { getServerStrings } from "@/lib/locale-server";

export async function generateMetadata(): Promise<Metadata> {
  const strings = await getServerStrings();
  return {
    title: strings.pages.data.title,
    description: strings.pages.data.description,
  };
}

export default function DataPage() {
  return <ConsolePage pageKey="data"><DataCatalog /></ConsolePage>;
}
