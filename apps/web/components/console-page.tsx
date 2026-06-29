"use client";

import type { ReactNode } from "react";

import { ConsoleTopbar } from "@/components/console-topbar";

type ConsolePageProps = {
  title: string;
  subtitle?: string;
  eyebrow?: string;
  sourceLabel?: string;
  controls?: ReactNode;
  children: ReactNode;
};

export function ConsolePage({
  title,
  subtitle,
  eyebrow,
  sourceLabel,
  controls,
  children,
}: ConsolePageProps) {
  return (
    <div className="ops-console">
      <ConsoleTopbar sourceLabel={sourceLabel} />
      <section className="ops-page-header">
        <div>
          {eyebrow ? <p className="section-label">{eyebrow}</p> : null}
          <h1 className="ops-page-title">{title}</h1>
          {subtitle ? <p className="ops-page-subtitle">{subtitle}</p> : null}
        </div>
        {controls ? (
          <div className="ops-controls" aria-label="Page controls">
            {controls}
          </div>
        ) : null}
      </section>
      <div className="ops-page-content">{children}</div>
    </div>
  );
}