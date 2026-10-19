"use client";

import Link from "next/link";
import { CircleHelp, ShieldCheck } from "lucide-react";

import {
  PopoverHeader,
  popoverClass,
  popoverRowClass,
  popoverRowLinkClass,
} from "@/components/topbar/panel-chrome";
import { cn } from "@/lib/cn";
import { useStrings } from "@/providers/locale-provider";

export function HelpPanel({ className }: { className?: string } = {}) {
  const strings = useStrings();
  return (
    <section className={className ?? popoverClass} aria-label={strings.ui.topbarHelpPanel.platformHelp}>
      <PopoverHeader label={strings.ui.topbarHelpPanel.platformHelp}>
        <span className="status-pill signal-ready">{strings.ui.topbarHelpPanel.docs}</span>
      </PopoverHeader>
      <div className="grid gap-2">
        <Link className={cn(popoverRowClass, popoverRowLinkClass)} href="/model-routing">
          <ShieldCheck size={16} />
          <span>
            <strong>{strings.ui.topbarHelpPanel.modelRouting}</strong>
            <small>{strings.ui.topbarHelpPanel.inspectProviderBoundariesAndEgress}</small>
          </span>
        </Link>
        <a
          className={cn(popoverRowClass, popoverRowLinkClass)}
          href="https://github.com/Limes-Labs/limes-axis/blob/main/docs/architecture.md"
          rel="noreferrer"
          target="_blank"
        >
          <CircleHelp size={16} />
          <span>
            <strong>{strings.ui.topbarHelpPanel.architectureDocs}</strong>
            <small>{strings.ui.topbarHelpPanel.openThePublicPlatformArchitecture}</small>
          </span>
        </a>
      </div>
    </section>
  );
}
