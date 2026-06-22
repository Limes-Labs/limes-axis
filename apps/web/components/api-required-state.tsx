"use client";

import { RadioTower } from "lucide-react";

type ApiRequiredStateProps = {
  detail: string;
  endpoint: string;
  title: string;
};

export function ApiRequiredState({ detail, endpoint, title }: ApiRequiredStateProps) {
  return (
    <section className="panel overview-context">
      <div>
        <p className="section-label">API Required</p>
        <h2 className="panel-title">{title}</h2>
        <p className="row-detail">{detail}</p>
        <p className="row-detail mono">{endpoint}</p>
      </div>
      <span className="status-pill signal-action-required">
        <RadioTower size={15} />
        API required
      </span>
    </section>
  );
}
