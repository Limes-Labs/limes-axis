import type { Metadata } from "next";
import { GeistMono } from "geist/font/mono";
import { GeistSans } from "geist/font/sans";
import type { ReactNode } from "react";

import { AppShell } from "@/components/app-shell";
import { THEME_STORAGE_KEY } from "@/lib/theme";
import { ThemeProvider } from "@/providers/theme-provider";

import "./globals.css";

export const metadata: Metadata = {
  title: "Axis Console",
  description: "The sovereign AI control plane for European operations.",
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

export default function RootLayout({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeInitScript }} />
      </head>
      <body className={`${GeistSans.variable} ${GeistMono.variable}`}>
        <ThemeProvider>
          <AppShell>{children}</AppShell>
        </ThemeProvider>
      </body>
    </html>
  );
}
