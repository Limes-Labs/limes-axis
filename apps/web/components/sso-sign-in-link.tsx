"use client";

import { useId, type ReactNode } from "react";

import { cn } from "@/lib/cn";
import { strings } from "@/lib/strings";
import { useBrowserSsoAvailability } from "@/lib/use-browser-sso";

/**
 * Every "Sign in with SSO" entry point. When the API's OIDC readiness report
 * says browser sign-in is not configured, the link would land the operator on
 * a raw `503` JSON page; it renders as a disabled control with a plain
 * explanation instead. Any other state keeps the real link.
 */
export function SsoSignInLink({
  href,
  className,
  children,
  gate = false,
}: {
  href: string;
  className: string;
  children: ReactNode;
  /** Marks the sign-in gate's primary action (`data-gate-sign-in`). */
  gate?: boolean;
}) {
  const availability = useBrowserSsoAvailability();
  const explanationId = useId();

  if (availability === "not_configured") {
    const copy = strings.identityGate.ssoNotConfigured;
    return (
      <span className="grid min-w-0 gap-1.5">
        <button
          aria-describedby={explanationId}
          className={cn(className, "cursor-not-allowed opacity-55")}
          data-gate-sign-in={gate || undefined}
          data-sso-not-configured
          disabled
          type="button"
        >
          {children}
        </button>
        <span className="text-xs leading-snug text-muted" id={explanationId}>
          <span className="font-medium text-ink">{copy.title}</span> {copy.detail}
        </span>
      </span>
    );
  }

  return (
    <a className={className} data-gate-sign-in={gate || undefined} href={href}>
      {children}
    </a>
  );
}
