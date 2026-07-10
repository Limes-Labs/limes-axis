"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ComponentType, ReactNode } from "react";
import {
  Bot,
  Building2,
  Cable,
  Gauge,
  Network,
  ReceiptText,
  ScrollText,
  Settings,
  ShieldCheck,
  Workflow,
} from "lucide-react";

import { AxisMark } from "@/components/axis-mark";
import { navigationItems, type NavigationItem } from "@/lib/foundation";
import { ConsoleProvider } from "@/providers/console-provider";

const iconMap: Record<NavigationItem["icon"], ComponentType<{ size?: number }>> = {
  gauge: Gauge,
  network: Network,
  workflow: Workflow,
  bot: Bot,
  shield: ShieldCheck,
  scroll: ScrollText,
  receipt: ReceiptText,
  cable: Cable,
  building: Building2,
  settings: Settings,
};

function isNavActive(pathname: string, href: string): boolean {
  if (href === "/") {
    return pathname === "/";
  }

  return pathname === href || pathname.startsWith(`${href}/`);
}

function Navigation({ pathname }: { pathname: string }) {
  return (
    <nav className="nav-list" aria-label="Axis sections">
      {navigationItems.map((item) => {
        const Icon = iconMap[item.icon];
        const active = isNavActive(pathname, item.href);

        return (
          <Link
            aria-current={active ? "page" : undefined}
            className={`nav-item${active ? " nav-item-active" : ""}`}
            href={item.href}
            key={item.href}
          >
            <Icon size={18} />
            <span>{item.label}</span>
          </Link>
        );
      })}
    </nav>
  );
}

function TopNavigation({ pathname }: { pathname: string }) {
  return (
    <div className="topbar">
      <div className="topnav" aria-label="Axis sections">
        {navigationItems.map((item) => {
          const Icon = iconMap[item.icon];
          const active = isNavActive(pathname, item.href);

          return (
            <Link
              aria-current={active ? "page" : undefined}
              className={`nav-item${active ? " nav-item-active" : ""}`}
              href={item.href}
              key={item.href}
            >
              <Icon size={18} />
              <span>{item.label}</span>
            </Link>
          );
        })}
      </div>
    </div>
  );
}

export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();

  return (
    <ConsoleProvider>
      <div className="app-shell">
        <aside className="sidebar" data-console-sidebar>
          <Link className="brand" href="/" aria-label="Limes Axis home">
            <AxisMark className="brand-mark-svg" />
            <span>
              <span className="brand-title font-display">Limes Axis</span>
              <span className="brand-subtitle">Control plane</span>
            </span>
          </Link>
          <Navigation pathname={pathname} />
        </aside>
        <main className="main">
          <TopNavigation pathname={pathname} />
          {children}
        </main>
      </div>
    </ConsoleProvider>
  );
}
