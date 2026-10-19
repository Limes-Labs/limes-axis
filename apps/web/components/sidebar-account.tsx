"use client";

import { HelpCircleIcon, Settings01Icon } from "@hugeicons/core-free-icons";
import { HugeiconsIcon } from "@hugeicons/react";
import Link from "next/link";
import {
  useCallback,
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
  type CSSProperties,
} from "react";

import { AccountPanel } from "@/components/topbar/account-panel";
import { HelpPanel } from "@/components/topbar/help-panel";
import { popoverClass, sidebarPopoverClass } from "@/components/topbar/panel-chrome";
import { cn } from "@/lib/cn";
import { announcePopoverOpened, useExclusivePopover } from "@/lib/console-popovers";
import { operatorInitials } from "@/lib/identity-format";
import type { IdentitySessionReadModel } from "@/lib/platform-overview";
import { useStrings } from "@/providers/locale-provider";
import { useOidcConsoleSession } from "@/lib/use-oidc-session";

type SidebarPanel = "account" | "help";

type RailAnchor = { left: number; bottom: number; maxHeight: number };

const RAIL_PANEL_GAP = 10;
const RAIL_PANEL_VIEWPORT_MARGIN = 16;

const footerRowClass =
  "flex min-h-[38px] w-full items-center gap-2.5 rounded-xl px-3 text-[13px] font-medium text-muted transition-colors hover:bg-signal/8 hover:text-ink";

/**
 * Identity and configuration live at the foot of the navigation rail rather
 * than the top-right corner: they are "who am I / how is this set up", which
 * belongs with navigation, while the topbar keeps state that changes as you
 * work (API health, provenance, refresh, search, notifications).
 */
export function SidebarAccount({
  identitySession,
  identitySessionUnavailable,
  settingsActive,
  variant = "rail",
}: {
  identitySession: IdentitySessionReadModel | null;
  identitySessionUnavailable: boolean;
  settingsActive: boolean;
  /**
   * `rail` is the sidebar footer. `compact` is the same controls as icon
   * buttons for viewports below 921px, where the sidebar is not rendered at all
   * and these would otherwise be unreachable.
   */
  variant?: "rail" | "compact";
}) {
  const strings = useStrings();
  const { session } = useOidcConsoleSession();
  const [activePanel, setActivePanel] = useState<SidebarPanel | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (activePanel === null) {
      return;
    }

    function onPointerDown(event: PointerEvent) {
      if (!containerRef.current?.contains(event.target as Node)) {
        setActivePanel(null);
      }
    }
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setActivePanel(null);
      }
    }

    document.addEventListener("pointerdown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("pointerdown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [activePanel]);

  useExclusivePopover(
    "sidebar-account",
    useCallback(() => setActivePanel(null), []),
  );

  // The rail's <aside> clips overflow so its nav list can scroll; a panel
  // positioned `absolute` inside it was cut at the 212px edge. A `fixed`
  // panel's containing block is the viewport (the aside has no transform or
  // filter), so it escapes the clip while staying in DOM and tab order next
  // to its trigger. Coordinates come from the footer's live rect.
  const [railAnchor, setRailAnchor] = useState<RailAnchor | null>(null);
  const railPanelOpen = variant === "rail" && activePanel !== null;
  useLayoutEffect(() => {
    if (!railPanelOpen) {
      return;
    }
    function measure() {
      const rect = containerRef.current?.getBoundingClientRect();
      if (!rect) {
        return;
      }
      setRailAnchor({
        left: rect.left + 4,
        bottom: window.innerHeight - rect.top + RAIL_PANEL_GAP,
        maxHeight: Math.max(rect.top - RAIL_PANEL_GAP - RAIL_PANEL_VIEWPORT_MARGIN, 160),
      });
    }
    measure();
    window.addEventListener("resize", measure);
    return () => window.removeEventListener("resize", measure);
  }, [railPanelOpen]);

  const actorId = identitySession?.actor_id ?? session?.actorId ?? null;
  const toggle = (panel: SidebarPanel) =>
    setActivePanel((current) => {
      const next = current === panel ? null : panel;
      if (next !== null) {
        announcePopoverOpened("sidebar-account");
      }
      return next;
    });
  const panelClass = variant === "rail" ? sidebarPopoverClass : popoverClass;

  if (variant === "compact") {
    return (
      <div className="relative flex items-center gap-1" ref={containerRef}>
        <Link
          aria-current={settingsActive ? "page" : undefined}
          aria-label={strings.pages.settings.title}
          className={cn("icon-button", settingsActive && "icon-button-active")}
          href="/settings"
        >
          <HugeiconsIcon icon={Settings01Icon} size={17} strokeWidth={1.8} />
        </Link>
        <button
          aria-expanded={activePanel === "help"}
          aria-label={strings.ui.sidebarAccount.openPlatformHelp}
          className={cn("icon-button", activePanel === "help" && "icon-button-active")}
          onClick={() => toggle("help")}
          title={strings.ui.sidebarAccount.openPlatformHelp}
          type="button"
        >
          <HugeiconsIcon icon={HelpCircleIcon} size={17} strokeWidth={1.8} />
        </button>
        <button
          aria-expanded={activePanel === "account"}
          aria-label={strings.shell.accountLabel(operatorInitials(actorId ?? undefined))}
          className={cn(
            "grid size-[34px] shrink-0 cursor-pointer place-items-center rounded-full border border-line bg-surface font-mono text-[11px] font-bold text-ink/80 transition-colors hover:border-signal/40 hover:bg-signal/10 dark:border-white/20 dark:bg-white/5",
            activePanel === "account" && "border-signal/40 bg-signal/10",
          )}
          data-operator-initials
          onClick={() => toggle("account")}
          title={strings.shell.account}
          type="button"
        >
          {operatorInitials(actorId ?? undefined)}
        </button>
        {activePanel === "help" ? <HelpPanel className={panelClass} /> : null}
        {activePanel === "account" ? (
          <AccountPanel
            className={panelClass}
            identitySession={identitySession}
            identitySessionUnavailable={identitySessionUnavailable}
          />
        ) : null}
      </div>
    );
  }

  return (
    <div
      className="relative mt-2 grid shrink-0 gap-1 border-t border-line pt-2 dark:border-white/10"
      ref={containerRef}
    >
      <Link
        aria-current={settingsActive ? "page" : undefined}
        className={cn(
          footerRowClass,
          settingsActive && "bg-tint-100 text-signal dark:bg-signal/15 dark:text-ink",
        )}
        href="/settings"
      >
        <HugeiconsIcon icon={Settings01Icon} size={18} strokeWidth={1.8} />
        <span>{strings.pages.settings.title}</span>
      </Link>

      <button
        aria-expanded={activePanel === "help"}
        aria-label={strings.ui.sidebarAccount.openPlatformHelp}
        className={cn(footerRowClass, activePanel === "help" && "bg-signal/10 text-ink")}
        onClick={() => toggle("help")}
        title={strings.ui.sidebarAccount.openPlatformHelp}
        type="button"
      >
        <HugeiconsIcon icon={HelpCircleIcon} size={18} strokeWidth={1.8} />
        <span>{strings.nav.help}</span>
      </button>

      <button
        aria-expanded={activePanel === "account"}
        aria-label={strings.shell.accountLabel(
          `${actorId ?? strings.nav.signedOut}, ${identitySession?.tenant_id ?? strings.nav.noTenant}`,
        )}
        className={cn(
          "mt-0.5 flex min-h-[46px] w-full cursor-pointer items-center gap-2.5 rounded-xl border border-line px-2 text-left transition-colors hover:border-signal/40 hover:bg-signal/8 dark:border-white/15",
          activePanel === "account" && "border-signal/40 bg-signal/10",
        )}
        onClick={() => toggle("account")}
        title={strings.shell.account}
        type="button"
      >
        <span
          aria-hidden="true"
          className="grid size-[28px] shrink-0 place-items-center rounded-full bg-tint-100 font-mono text-[11px] font-bold text-signal dark:bg-signal/20 dark:text-white"
          data-operator-initials
        >
          {operatorInitials(actorId ?? undefined)}
        </span>
        <span className="grid min-w-0">
          <span className="truncate text-[12px] font-semibold text-ink">
            {actorId ?? strings.nav.signedOut}
          </span>
          <span className="truncate text-[10.5px] text-muted">
            {identitySession?.tenant_id ?? strings.nav.noTenant}
          </span>
        </span>
      </button>

      {activePanel !== null ? (
        <div
          className="fixed z-70"
          data-sidebar-popover
          style={
            {
              left: railAnchor?.left ?? 0,
              bottom: railAnchor?.bottom ?? 0,
              // Hidden for the single pre-measure render so it never flashes
              // at the viewport corner.
              visibility: railAnchor ? undefined : "hidden",
              "--sidebar-popover-max-h": railAnchor
                ? `${railAnchor.maxHeight}px`
                : undefined,
            } as CSSProperties
          }
        >
          {activePanel === "help" ? <HelpPanel className={panelClass} /> : null}
          {activePanel === "account" ? (
            <AccountPanel
              className={panelClass}
              identitySession={identitySession}
              identitySessionUnavailable={identitySessionUnavailable}
            />
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
