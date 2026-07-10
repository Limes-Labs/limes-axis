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
    <section className="panel overview-context api-required-card">
      <div>
        <p className="section-label">API Required</p>
        <h2 className="panel-title">{title}</h2>
        <p className="row-detail">{detail}</p>
        <p className="row-detail mono api-required-endpoints">{endpoint}</p>
      </div>
      <span className="status-pill signal-action-required">
        <RadioTower size={15} />
        API required
      </span>
      <AxisMark className="api-required-mark" />
    </section>
  );
}
