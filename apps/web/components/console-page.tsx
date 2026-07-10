"use client";

import type { ReactNode } from "react";

import { ConsoleTopbar } from "@/components/console-topbar";
import { Eyebrow } from "@/components/ui/eyebrow";

type ConsolePageProps = {
  title: string;
  subtitle?: string;
  eyebrow?: string;
  sourceLabel?: string;
  controls?: ReactNode;
  children: ReactNode;
};

/** Two-tone page title: the first word renders in Signal Blue. */
function splitTitle(title: string): { lead: string; rest: string } {
  const [lead = "", ...rest] = title.trim().split(/\s+/);
  return { lead, rest: rest.join(" ") };
}

export function ConsolePage({
  title,
  subtitle,
  eyebrow,
  sourceLabel,
  controls,
  children,
}: ConsolePageProps) {
  const { lead, rest } = splitTitle(title);

  return (
    <div className="ops-console grid min-h-screen content-start gap-3 px-4 pb-5 sm:px-6">
      <ConsoleTopbar sourceLabel={sourceLabel} />
      <section className="flex min-w-0 flex-wrap items-center justify-between gap-4">
        <div>
          {eyebrow ? <Eyebrow>{eyebrow}</Eyebrow> : null}
          <h1 className="font-display m-0 text-[26px] text-ink">
            {rest ? (
              <>
                <span className="text-signal">{lead} </span>
                {rest}
              </>
            ) : (
              lead
            )}
          </h1>
          {subtitle ? (
            <p className="ops-page-subtitle mx-0 mt-1.5 mb-0 max-w-3xl text-[13px] leading-snug text-muted">
              {subtitle}
            </p>
          ) : null}
        </div>
        {controls ? (
          <div className="flex flex-wrap items-center justify-end gap-2" aria-label="Page controls">
            {controls}
          </div>
        ) : null}
      </section>
      <div aria-hidden="true" className="rule-dotted mt-0.5" />
      <div className="grid min-w-0 gap-3.5">{children}</div>
    </div>
  );
}
