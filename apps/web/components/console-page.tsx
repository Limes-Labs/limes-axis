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
    <div className="ops-console">
      <ConsoleTopbar sourceLabel={sourceLabel} />
      <section className="ops-page-header">
        <div>
          {eyebrow ? <Eyebrow className="section-label">{eyebrow}</Eyebrow> : null}
          <h1 className="ops-page-title font-display">
            {rest ? (
              <>
                <span className="ops-page-title-lead">{lead} </span>
                {rest}
              </>
            ) : (
              lead
            )}
          </h1>
          {subtitle ? <p className="ops-page-subtitle">{subtitle}</p> : null}
        </div>
        {controls ? (
          <div className="ops-controls" aria-label="Page controls">
            {controls}
          </div>
        ) : null}
      </section>
      <div aria-hidden="true" className="rule-dotted ops-page-rule" />
      <div className="ops-page-content">{children}</div>
    </div>
  );
}
