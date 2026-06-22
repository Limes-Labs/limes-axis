import type { Metadata } from "next";
import Link from "next/link";
import type { ComponentType, ReactNode } from "react";
import {
  Bot,
  Cable,
  Gauge,
  Network,
  ReceiptText,
  ShieldCheck,
  Workflow,
} from "lucide-react";

import { navigationItems, type NavigationItem } from "@/lib/foundation";

import "./globals.css";

export const metadata: Metadata = {
  title: "Axis Console",
  description: "The sovereign AI control plane for European operations.",
};

const iconMap: Record<NavigationItem["icon"], ComponentType<{ size?: number }>> = {
  gauge: Gauge,
  network: Network,
  workflow: Workflow,
  bot: Bot,
  shield: ShieldCheck,
  receipt: ReceiptText,
  cable: Cable,
};

function Navigation() {
  return (
    <nav className="nav-list" aria-label="Axis sections">
      {navigationItems.map((item) => {
        const Icon = iconMap[item.icon];

        return (
          <Link className="nav-item" href={item.href} key={item.href}>
            <Icon size={18} />
            <span>{item.label}</span>
          </Link>
        );
      })}
    </nav>
  );
}

function TopNavigation() {
  return (
    <div className="topbar">
      <div className="topnav" aria-label="Axis sections">
        {navigationItems.map((item) => {
          const Icon = iconMap[item.icon];

          return (
            <Link className="nav-item" href={item.href} key={item.href}>
              <Icon size={18} />
              <span>{item.label}</span>
            </Link>
          );
        })}
      </div>
    </div>
  );
}

export default function RootLayout({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <html lang="en">
      <body>
        <div className="app-shell">
          <aside className="sidebar">
            <Link className="brand" href="/">
              <span className="brand-mark">AX</span>
              <span>
                <span className="brand-title">Limes Axis</span>
                <span className="brand-subtitle">Control plane</span>
              </span>
            </Link>
            <Navigation />
          </aside>
          <main className="main">
            <TopNavigation />
            {children}
          </main>
        </div>
      </body>
    </html>
  );
}
