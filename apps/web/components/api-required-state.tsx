"use client";

import { RadioTower } from "lucide-react";

import { AxisMark } from "@/components/axis-mark";

type ApiRequiredStateProps = {
  detail: string;
  endpoint: string;
  title: string;
};

export function ApiRequiredState({ detail, endpoint, title }: ApiRequiredStateProps) {
  return (
    <section className="relative flex min-w-0 flex-wrap items-start justify-between gap-4 overflow-hidden rounded-2xl border border-dashed border-slate/45 bg-surface/55 p-4.5 dark:border-white/20 dark:bg-white/4">
      <div>
        <p className="eyebrow m-0">API Required</p>
        <h2 className="font-display mx-0 mt-2 mb-1.5 text-xl text-ink">{title}</h2>
        <p className="m-0 max-w-2xl text-sm leading-snug text-muted">{detail}</p>
        <p className="mx-0 mt-1.5 mb-0 font-mono text-xs break-words text-muted">{endpoint}</p>
      </div>
      <span className="status-pill signal-action-required">
        <RadioTower size={15} />
        API required
      </span>
      <AxisMark className="pointer-events-none absolute -right-3.5 -bottom-4.5 h-[108px] w-[108px] text-ink opacity-10" />
    </section>
  );
}
