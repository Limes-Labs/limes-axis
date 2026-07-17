"use client";

import { useEffect, useMemo, useState } from "react";
import { Bell, CircleHelp, RefreshCw, Search, ShieldCheck } from "lucide-react";

import { ConsoleCommandMenu } from "@/components/console-command-menu";
import { DemoBadge } from "@/components/demo-badge";
import { ThemeToggle } from "@/components/theme-toggle";
import { AccountPanel } from "@/components/topbar/account-panel";
import { HelpPanel } from "@/components/topbar/help-panel";
import { NotificationPanel } from "@/components/topbar/notification-panel";
import { cn } from "@/lib/cn";
import { apiStatusClass, operatorInitials } from "@/lib/identity-format";
import type {
  IdentitySessionReadModel,
  ManufacturingNotificationCenter,
} from "@/lib/platform-overview";
import { useAxisQuery } from "@/lib/use-axis-query";
import {
  parseIdentitySessionReadModel,
  parseManufacturingNotificationCenter,
} from "@/lib/runtime-contracts/overview";
import {
  buildTenantScopedPath,
  DEMO_TENANT_ID,
  resolveConsoleTenantScope,
} from "@/lib/tenant-scope";
import { useOidcConsoleSession } from "@/lib/use-oidc-session";
import { useConsole } from "@/providers/console-provider";

type TopbarPanel = "notifications" | "help" | "account" | null;

export function ConsoleTopbar({
  sourceLabel,
  evidenceLabel,
}: {
  sourceLabel?: string;
  evidenceLabel?: string;
}) {
  const { apiStatus, triggerRefresh } = useConsole();
  const [commandMenuOpen, setCommandMenuOpen] = useState(false);
  const [activePanel, setActivePanel] = useState<TopbarPanel>(null);
  const { session } = useOidcConsoleSession();
  const { data: identitySession, isUnavailable: identitySessionUnavailable } =
    useAxisQuery<IdentitySessionReadModel>("/identity/session", {
      parse: parseIdentitySessionReadModel,
    });
  const tenantScope = resolveConsoleTenantScope(identitySession);
  const tenantId = tenantScope.tenantId;
  const { data: notificationCenter } = useAxisQuery<ManufacturingNotificationCenter>(
    buildTenantScopedPath(
      "/demo/manufacturing/notifications",
      tenantId ?? DEMO_TENANT_ID,
    ),
    {
      enabled: tenantId !== null,
      expectedTenantId: tenantId ?? undefined,
      parse: parseManufacturingNotificationCenter,
    },
  );

  const notificationCount = useMemo(() => {
    if (!notificationCenter) {
      return 0;
    }

    return Math.min(9, notificationCenter.unread_count);
  }, [notificationCenter]);

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      const target = event.target as HTMLElement | null;
      const isTextInput =
        target?.tagName === "INPUT" ||
        target?.tagName === "TEXTAREA" ||
        target?.isContentEditable;

      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setActivePanel(null);
        setCommandMenuOpen(true);
        return;
      }

      if (!isTextInput && event.key === "/") {
        event.preventDefault();
        setActivePanel(null);
        setCommandMenuOpen(true);
      }

      if (event.key === "Escape") {
        setActivePanel(null);
      }
    }

    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, []);

  return (
    <header
      className="ops-topbar sticky top-0 isolate z-10 -mx-4 flex min-h-[62px] flex-wrap items-center gap-x-4 gap-y-2 border-b border-line bg-surface/80 px-4 py-2 backdrop-blur-xl max-sm:grid max-sm:min-h-0 max-sm:grid-cols-[minmax(0,1fr)_auto] max-sm:gap-2 max-sm:py-1.5 sm:-mx-6 sm:px-6 dark:border-white/10"
      aria-label="Console status bar"
    >
      <div className="hidden min-w-0 flex-1 sm:block">
        <span className="flex items-center gap-2.5 text-xs font-semibold text-ink/80 [&>svg]:text-positive">
          <ShieldCheck size={17} />
          Sovereign Control
        </span>
      </div>
      <div className="flex min-w-0 flex-wrap items-center gap-2 max-sm:flex-nowrap max-sm:overflow-x-auto max-sm:pb-px max-sm:[&_.status-pill]:px-2 max-sm:[&_.status-pill]:text-[11px] max-sm:[&_.status-pill]:whitespace-nowrap sm:ml-auto sm:justify-end">
        <span className={`status-pill ${apiStatusClass(apiStatus.state)}`} title={apiStatus.detail}>
          <span aria-hidden="true" className={`status-dot ${apiStatusClass(apiStatus.state)}`} />
          API {apiStatus.label}
        </span>
        <DemoBadge
          enabled={tenantScope.mode === "demo"}
          tenantId={tenantId ?? DEMO_TENANT_ID}
        />
        {sourceLabel ? (
          <span className="status-pill signal-ready">{sourceLabel}</span>
        ) : null}
        {evidenceLabel ? (
          <span className="status-pill signal-ready">{evidenceLabel}</span>
        ) : null}
      </div>
      <div
        className="ops-toolbar-icons flex min-w-0 flex-wrap items-center justify-end gap-2 max-sm:flex-nowrap max-sm:gap-1"
        aria-label="Utility actions"
      >
        <button
          className="icon-button"
          type="button"
          aria-label="Refresh state"
          title="Refresh state"
          onClick={triggerRefresh}
        >
          <RefreshCw size={17} />
        </button>
        <ThemeToggle />
        <button
          className="icon-button"
          type="button"
          aria-label="Search console"
          title="Search console"
          onClick={() => {
            setActivePanel(null);
            setCommandMenuOpen(true);
          }}
        >
          <Search size={17} />
        </button>
        <button
          className={`icon-button${activePanel === "notifications" ? " icon-button-active" : ""}`}
          type="button"
          aria-expanded={activePanel === "notifications"}
          aria-label="Open notifications"
          title="Open notifications"
          onClick={() =>
            setActivePanel((current) => (current === "notifications" ? null : "notifications"))
          }
        >
          <Bell size={17} />
          {notificationCount > 0 ? (
            <span className="absolute top-1 right-1 grid h-[14px] min-w-[14px] place-items-center rounded-full border border-surface bg-positive px-0.5 font-mono text-[9px] leading-none font-extrabold text-white">
              {notificationCount}
            </span>
          ) : null}
        </button>
        <button
          className={`icon-button${activePanel === "help" ? " icon-button-active" : ""}`}
          type="button"
          aria-expanded={activePanel === "help"}
          aria-label="Open platform help"
          title="Open platform help"
          onClick={() => setActivePanel((current) => (current === "help" ? null : "help"))}
        >
          <CircleHelp size={17} />
        </button>
        <span className="mx-0.5 h-[22px] w-px shrink-0 bg-line dark:bg-white/15" aria-hidden="true" />
        <button
          className={cn(
            "grid size-[34px] shrink-0 cursor-pointer place-items-center rounded-full border border-line bg-surface text-xs font-bold text-ink/80 transition-colors hover:border-signal/40 hover:bg-signal/10 active:translate-y-px dark:border-white/20 dark:bg-white/5",
            activePanel === "account" && "border-signal/40 bg-signal/10",
          )}
          type="button"
          aria-expanded={activePanel === "account"}
          aria-label="Open operator account"
          title="Open operator account"
          onClick={() => setActivePanel((current) => (current === "account" ? null : "account"))}
        >
          {operatorInitials(identitySession?.actor_id ?? session?.actorId)}
        </button>
        {activePanel === "notifications" ? (
          <NotificationPanel
            center={notificationCenter}
            identitySession={identitySession}
            onAcknowledged={triggerRefresh}
            session={session}
          />
        ) : null}
        {activePanel === "help" ? <HelpPanel /> : null}
        {activePanel === "account" ? (
          <AccountPanel
            identitySession={identitySession}
            identitySessionUnavailable={identitySessionUnavailable}
          />
        ) : null}
      </div>
      <ConsoleCommandMenu
        apiLabel={apiStatus.label}
        onClose={() => setCommandMenuOpen(false)}
        onRefresh={triggerRefresh}
        open={commandMenuOpen}
      />
    </header>
  );
}
