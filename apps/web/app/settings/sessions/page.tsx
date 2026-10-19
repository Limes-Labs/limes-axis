import type { Metadata } from "next";

import { SessionSecurityConsole } from "@/components/session-security-console";
import { getServerStrings } from "@/lib/locale-server";

export async function generateMetadata(): Promise<Metadata> {
  const strings = await getServerStrings();
  return {
    title: strings.ui.detailPages.sessionsTitle,
    description: strings.ui.detailPages.sessionsDescription,
  };
}

export default function SessionsPage() {
  return <SessionSecurityConsole />;
}
