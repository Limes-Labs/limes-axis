import type { Metadata, Viewport } from "next";
import { GeistMono } from "geist/font/mono";
import { GeistSans } from "geist/font/sans";
import type { ReactNode } from "react";

import { AppShell } from "@/components/app-shell";
import { getRequestLocale, getServerStrings } from "@/lib/locale-server";
import { THEME_STORAGE_KEY } from "@/lib/theme";
import { LocaleProvider } from "@/providers/locale-provider";
import { ThemeProvider } from "@/providers/theme-provider";

import "./globals.css";

export async function generateMetadata(): Promise<Metadata> {
  const copy = (await getServerStrings()).ui.rootLayout;
  return {
    /*
     * Operators keep Approvals, Audit and a policy detail open side by side, so
     * every tab needs its own name. Pages supply the `%s`.
     */
    title: {
      default: copy.title,
      template: copy.titleTemplate,
    },
    description: copy.description,
    // A tenant governance console must never be indexed — staging deploys are
    // how that leaks.
    robots: { index: false, follow: false },
  };
}

export const viewport: Viewport = {
  // Matches --cloud / --bg in globals.css so mobile browser chrome tracks the
  // console's own theme.
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#f7f8fb" },
    { media: "(prefers-color-scheme: dark)", color: "#04122e" },
  ],
};

/**
 * No-FOUC theme bootstrap: resolve the stored preference (or the OS scheme)
 * to "light"/"dark" and stamp it on <html> before first paint. Mirrors
 * `resolveTheme` in lib/theme.ts.
 */
const themeInitScript = `(function () {
  try {
    var stored = localStorage.getItem(${JSON.stringify(THEME_STORAGE_KEY)});
    var preference = stored === "light" || stored === "dark" || stored === "system" ? stored : "system";
    var resolved = preference === "system"
      ? (window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light")
      : preference;
    document.documentElement.dataset.theme = resolved;
  } catch (error) {
    document.documentElement.dataset.theme = "light";
  }
})();`;

export default async function RootLayout({ children }: Readonly<{ children: ReactNode }>) {
  // Cookie, then Accept-Language, then English: the same resolution the
  // pages use, so `<html lang>` always names the language on screen.
  const locale = await getRequestLocale();

  return (
    <html lang={locale} suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeInitScript }} />
      </head>
      <body className={`${GeistSans.variable} ${GeistMono.variable}`}>
        <LocaleProvider locale={locale}>
          <ThemeProvider>
            <AppShell>{children}</AppShell>
          </ThemeProvider>
        </LocaleProvider>
      </body>
    </html>
  );
}
