"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";

import { AxisMark } from "@/components/axis-mark";
import { MobileNavigation } from "@/components/mobile-navigation";
import { navIconMap } from "@/components/nav-icons";
import { SidebarAccount } from "@/components/sidebar-account";
import { SignInGate } from "@/components/sign-in-gate";
import { countAwaitingDecision, type ManufacturingApprovalInbox } from "@/lib/approval-demo";
import { cn } from "@/lib/cn";
import { strings } from "@/lib/strings";
import { ToastProvider } from "@/components/ui/toast";
import { desktopNavGroups, isNavActive, type NavItem } from "@/lib/nav";
import { useAxisQuery } from "@/lib/use-axis-query";
import { parseManufacturingApprovalInbox } from "@/lib/runtime-contracts/approvals";
import {
  startIdentitySessionHeartbeat,
  useIdentitySession,
} from "@/lib/use-identity-session";
import {
  buildTenantScopedPath,
  DEMO_TENANT_ID,
  resolveConsoleTenantScope,
  OPERATIONS_API_PREFIX,
} from "@/lib/tenant-scope";
import { ConsoleProvider } from "@/providers/console-provider";
import {
  resolveVocabularyTenantId,
  TenantVocabularyProvider,
} from "@/providers/tenant-vocabulary-provider";

const navItemClass =
  "flex min-h-[44px] items-center gap-2.5 rounded-xl px-3 text-[13px] font-medium text-muted transition-colors hover:bg-signal/8 hover:text-ink";
const navItemActiveClass =
  "bg-tint-100 text-signal shadow-[inset_2px_0_0_rgb(var(--signal))] hover:bg-tint-100 hover:text-signal dark:bg-signal/15 dark:text-ink dark:hover:bg-signal/15 dark:hover:text-ink";

/**
 * Pending-approvals count pill next to the Approvals nav label. Best-effort:
 * while loading or when the API is unavailable it renders nothing.
 */
function ApprovalsBadge({
  identitySource,
  tenantId,
}: {
  identitySource: string;
  tenantId: string | null;
}) {
  const { data } = useAxisQuery<ManufacturingApprovalInbox>(
    buildTenantScopedPath(
      `${OPERATIONS_API_PREFIX}/approvals`,
      tenantId ?? DEMO_TENANT_ID,
    ),
    {
      enabled: identitySource === "api" && tenantId !== null,
      expectedTenantId: tenantId ?? undefined,
      parse: parseManufacturingApprovalInbox,
    },
  );
  const pendingCount = countAwaitingDecision(data);

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
  badge,
  item,
  pathname,
  className,
}: {
  badge?: ReactNode;
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
      {item.badge === "approvals" ? badge : null}
    </Link>
  );
}

type NavOverflow = { above: boolean; below: boolean };

/**
 * Tracks whether the rail's nav list has items scrolled out of view above or
 * below. Overlay scrollbars (macOS, touch) give no cue on their own, so the
 * shell fades whichever edge still has content behind it.
 */
function useNavOverflow() {
  const ref = useRef<HTMLElement>(null);
  const [overflow, setOverflow] = useState<NavOverflow>({
    above: false,
    below: false,
  });

  const measure = useCallback(() => {
    const element = ref.current;
    if (!element) {
      return;
    }
    const above = element.scrollTop > 1;
    const below =
      element.scrollTop + element.clientHeight < element.scrollHeight - 1;
    setOverflow((current) =>
      current.above === above && current.below === below
        ? current
        : { above, below },
    );
  }, []);

  useEffect(() => {
    const element = ref.current;
    if (!element) {
      return;
    }
    measure();
    element.addEventListener("scroll", measure, { passive: true });
    window.addEventListener("resize", measure);
    const observer =
      typeof ResizeObserver === "undefined" ? null : new ResizeObserver(measure);
    observer?.observe(element);
    return () => {
      element.removeEventListener("scroll", measure);
      window.removeEventListener("resize", measure);
      observer?.disconnect();
    };
  }, [measure]);

  return { overflow, ref };
}

const navFadeClass =
  "pointer-events-none absolute inset-x-0 z-1 h-10 from-surface to-transparent transition-opacity duration-200";

function Navigation({
  badge,
  pathname,
}: {
  badge: ReactNode;
  pathname: string;
}) {
  const { overflow, ref } = useNavOverflow();

  // On a short viewport the current section can sit below the fold (Tenants
  // at 900px tall); bring it into the rail's view on every route change.
  useEffect(() => {
    const active = ref.current?.querySelector<HTMLElement>("[aria-current='page']");
    active?.scrollIntoView?.({ block: "nearest" });
  }, [pathname, ref]);

  return (
    <div
      className="relative flex min-h-0 grow flex-col"
      data-nav-overflow-above={overflow.above ? "" : undefined}
      data-nav-overflow-below={overflow.below ? "" : undefined}
    >
      <nav
        // scroll-py matches the fade height so a scrolled-to item is never
        // left underneath an edge fade.
        className="nav-list grid min-h-0 grow scroll-py-10 content-start gap-1 overflow-y-auto overscroll-contain pr-1 pb-1"
        aria-label="Axis sections"
        ref={ref}
      >
        {desktopNavGroups.map((group, index) => (
          <section
            aria-label={group.label}
            className="grid gap-1"
            key={group.label}
          >
            <span className={cn("eyebrow px-3", index === 0 ? "pt-1" : "pt-3")}>
              {group.label}
            </span>
            {group.items.map((item) => (
              <NavLink
                badge={badge}
                item={item}
                key={item.href}
                pathname={pathname}
              />
            ))}
          </section>
        ))}
      </nav>
      {/* Edge cues: a top hairline + fade once scrolled, and a bottom fade
          with a chevron while items remain below the fold. */}
      <div
        aria-hidden="true"
        className={cn(
          navFadeClass,
          "top-0 border-t border-line bg-linear-to-b dark:border-white/10",
          overflow.above ? "opacity-100" : "opacity-0",
        )}
      />
      <div
        aria-hidden="true"
        className={cn(
          navFadeClass,
          "bottom-0 flex items-end justify-center bg-linear-to-t pb-0.5 text-muted",
          overflow.below ? "opacity-100" : "opacity-0",
        )}
      >
        <svg fill="none" height="14" viewBox="0 0 12 12" width="14">
          <path
            d="M3 4.5 6 7.5l3-3"
            stroke="currentColor"
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth="1.5"
          />
        </svg>
      </div>
    </div>
  );
}

/**
 * Shell body. Split from `AppShell` because it reads console context via
 * `useIdentitySession`, and `AppShell` is the component that mounts the
 * provider — calling the hook there runs it outside the provider it is
 * creating.
 */
function ConsoleShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const identity = useIdentitySession();
  const tenantScope = resolveConsoleTenantScope(identity.data);
  const vocabularyTenantId = resolveVocabularyTenantId(pathname, tenantScope.tenantId);
  // One bounded background loop for enforced-SSO deployments: it re-verifies
  // the session so an expiry or revocation converges to the sign-in gate
  // promptly instead of waiting for the next unrelated request.
  useEffect(() => startIdentitySessionHeartbeat(), []);
  // One gate for enforced-SSO deployments: when the API says "sign-in
  // required" and no session verified, surfaces never mount — so no surface
  // can render generic error panels or stale tenant data behind the gate.
  const signInRequired =
    identity.source === "api"
    && identity.data !== null
    && identity.data.api_auth_required
    && !identity.data.authenticated;
  // Behind the gate no tenant scope exists yet; the demo-tenant fallback would
  // only produce doomed 401 requests from the shell chrome.
  const approvalsBadge = signInRequired ? null : (
    <ApprovalsBadge
      identitySource={identity.source}
      tenantId={tenantScope.tenantId}
    />
  );

  return (
    <TenantVocabularyProvider
      enabled={!signInRequired && identity.source === "api" && vocabularyTenantId !== null}
      tenantId={vocabularyTenantId}
    >
      <>
        <a
          className="fixed top-2 left-2 z-50 -translate-y-20 rounded-lg bg-ink px-4 py-2 text-sm font-medium text-surface shadow-lg transition-transform focus:translate-y-0"
          href="#console-main"
        >
          Skip to main content
        </a>
        <div className="grid min-h-screen grid-cols-1 min-[921px]:grid-cols-[212px_minmax(0,1fr)]">
          <aside
            className="sidebar fixed inset-y-0 left-0 z-12 hidden h-dvh min-h-0 w-[212px] flex-col overflow-hidden border-r border-line bg-surface px-2.5 pt-4 pb-3 min-[921px]:flex dark:border-white/10"
            data-console-sidebar
          >
            <Link
              className="mb-3.5 flex min-h-[44px] shrink-0 items-center gap-3 border-b border-line px-1.5 pb-3.5 dark:border-white/10"
              href="/"
              aria-label={strings.shell.homeLink}
            >
              <AxisMark className="h-[30px] w-[30px] shrink-0 text-ink" />
              <span>
                <span className="font-display block text-base text-ink">
                  {strings.shell.brand}
                </span>
                <span className="mt-0.5 block font-mono text-[11px] font-medium tracking-[0.14em] text-muted uppercase">
                  {strings.shell.controlPlane}
                </span>
              </span>
            </Link>
            <Navigation badge={approvalsBadge} pathname={pathname} />
            <SidebarAccount
              identitySession={identity.data}
              identitySessionUnavailable={identity.source === "unavailable"}
              settingsActive={isNavActive(pathname, "/settings")}
            />
          </aside>
          <main
            className="min-w-0 min-[921px]:col-start-2"
            id="console-main"
            tabIndex={-1}
          >
            <MobileNavigation badge={approvalsBadge} pathname={pathname} />
            {signInRequired && identity.data ? (
              <SignInGate identitySession={identity.data} />
            ) : (
              children
            )}
          </main>
        </div>
      </>
    </TenantVocabularyProvider>
  );
}

export function AppShell({ children }: { children: ReactNode }) {
  return (
    <ConsoleProvider>
      <ToastProvider>
        <ConsoleShell>{children}</ConsoleShell>
      </ToastProvider>
    </ConsoleProvider>
  );
}
