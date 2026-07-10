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
import { cn } from "@/lib/cn";
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

const navItemClass =
  "flex min-h-[44px] items-center gap-2.5 rounded-xl px-3 text-[13px] font-medium text-muted transition-colors hover:bg-signal/8 hover:text-ink";
const navItemActiveClass =
  "bg-tint-100 text-signal shadow-[inset_2px_0_0_rgb(var(--signal))] hover:bg-tint-100 hover:text-signal dark:bg-signal/15 dark:text-ink dark:hover:bg-signal/15 dark:hover:text-ink";

function isNavActive(pathname: string, href: string): boolean {
  if (href === "/") {
    return pathname === "/";
  }

  return pathname === href || pathname.startsWith(`${href}/`);
}

function Navigation({ pathname }: { pathname: string }) {
  return (
    <nav
      className="nav-list grid min-h-0 grow content-start gap-1.5 overflow-y-auto overscroll-contain pr-1 pb-1"
      aria-label="Axis sections"
    >
      {navigationItems.map((item) => {
        const Icon = iconMap[item.icon];
        const active = isNavActive(pathname, item.href);

        return (
          <Link
            aria-current={active ? "page" : undefined}
            className={cn(navItemClass, active && navItemActiveClass)}
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
    <div className="sticky top-0 z-10 block overflow-hidden border-b border-line bg-surface/90 px-3 py-2.5 backdrop-blur-md min-[921px]:hidden dark:border-white/10">
      <div
        className="topnav flex max-w-full min-w-0 gap-1.5 overflow-x-auto pb-0.5"
        aria-label="Axis sections"
      >
        {navigationItems.map((item) => {
          const Icon = iconMap[item.icon];
          const active = isNavActive(pathname, item.href);

          return (
            <Link
              aria-current={active ? "page" : undefined}
              className={cn(navItemClass, "shrink-0", active && navItemActiveClass)}
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
      <div className="grid min-h-screen grid-cols-1 min-[921px]:grid-cols-[190px_minmax(0,1fr)]">
        <aside
          className="sidebar fixed inset-y-0 left-0 z-12 hidden h-dvh min-h-0 w-[190px] flex-col overflow-hidden border-r border-line bg-surface px-2.5 py-4 min-[921px]:flex dark:border-white/10"
          data-console-sidebar
        >
          <Link
            className="mb-3.5 flex min-h-[44px] items-center gap-3 border-b border-line px-1.5 pb-3.5 dark:border-white/10"
            href="/"
            aria-label="Limes Axis home"
          >
            <AxisMark className="h-[30px] w-[30px] shrink-0 text-ink" />
            <span>
              <span className="font-display block text-base text-ink">Limes Axis</span>
              <span className="mt-0.5 block font-mono text-[9px] font-medium tracking-[0.18em] text-muted uppercase">
                Control plane
              </span>
            </span>
          </Link>
          <Navigation pathname={pathname} />
        </aside>
        <main className="min-w-0 min-[921px]:col-start-2">
          <TopNavigation pathname={pathname} />
          {children}
        </main>
      </div>
    </ConsoleProvider>
  );
}
