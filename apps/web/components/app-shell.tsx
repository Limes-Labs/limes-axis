"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

import { AxisMark } from "@/components/axis-mark";
import { navIconMap } from "@/components/nav-icons";
import type { ManufacturingApprovalInbox } from "@/lib/approval-demo";
import { cn } from "@/lib/cn";
import { ToastProvider } from "@/components/ui/toast";
import { navGroups, navItems, type NavItem } from "@/lib/nav";
import { useAxisQuery } from "@/lib/use-axis-query";
import { parseManufacturingApprovalInbox } from "@/lib/runtime-contracts/approvals";
import { ConsoleProvider } from "@/providers/console-provider";

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

/**
 * Pending-approvals count pill next to the Approvals nav label. Best-effort:
 * while loading or when the API is unavailable it renders nothing.
 */
function ApprovalsBadge() {
  const { data } = useAxisQuery<ManufacturingApprovalInbox>("/demo/manufacturing/approvals", {
    parse: parseManufacturingApprovalInbox,
  });
  const pendingCount =
    data?.approvals?.filter((approval) => approval.status === "pending").length ?? 0;

  if (pendingCount === 0) {
    return null;
  }

  return (
    <span
      aria-label={`${pendingCount} pending approvals`}
      className="ml-auto inline-flex h-[18px] min-w-[18px] items-center justify-center rounded-full bg-signal px-1.5 font-mono text-[10px] leading-none font-bold text-white"
    >
      {pendingCount > 9 ? "9+" : pendingCount}
    </span>
  );
}

function NavLink({
  item,
  pathname,
  className,
}: {
  item: NavItem;
  pathname: string;
  className?: string;
}) {
  const Icon = navIconMap[item.icon];
  const active = isNavActive(pathname, item.href);

  return (
    <Link
      aria-current={active ? "page" : undefined}
      className={cn(navItemClass, className, active && navItemActiveClass)}
      href={item.href}
    >
      <Icon size={18} />
      <span>{item.label}</span>
      {item.badge === "approvals" ? <ApprovalsBadge /> : null}
    </Link>
  );
}

function Navigation({ pathname }: { pathname: string }) {
  return (
    <nav
      className="nav-list grid min-h-0 grow content-start gap-1 overflow-y-auto overscroll-contain pr-1 pb-1"
      aria-label="Axis sections"
    >
      {navGroups.map((group, index) => (
        <section aria-label={group.label} className="grid gap-1" key={group.label}>
          <span className={cn("eyebrow px-3", index === 0 ? "pt-1" : "pt-3")}>{group.label}</span>
          {group.items.map((item) => (
            <NavLink item={item} key={item.href} pathname={pathname} />
          ))}
        </section>
      ))}
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
        {navItems.map((item) => (
          <NavLink className="shrink-0" item={item} key={item.href} pathname={pathname} />
        ))}
      </div>
    </div>
  );
}

export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();

  return (
    <ConsoleProvider>
      <ToastProvider>
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
      </ToastProvider>
    </ConsoleProvider>
  );
}
