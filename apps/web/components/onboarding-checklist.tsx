"use client";

import { useState } from "react";
import Link from "next/link";
import { ChevronDown, ChevronRight, CircleCheckBig, Circle } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { Eyebrow } from "@/components/ui/eyebrow";
import { cn } from "@/lib/cn";
import type { ManufacturingAgentRegistry } from "@/lib/agent-demo";
import type { ManufacturingConnectorRegistry } from "@/lib/connectors-demo";
import type { ManufacturingOntology } from "@/lib/ontology-demo";
import type { PlatformPolicyRegistry } from "@/lib/platform-policies";
import { strings } from "@/lib/strings";
import { useAxisQuery } from "@/lib/use-axis-query";
import type { ManufacturingWorkflowConsole } from "@/lib/workflow-demo";

/*
 * Guided setup checklist (spec §6): five steps from an empty tenant to a
 * governed workflow. Done-state is derived client-side from the registry
 * endpoints, best-effort — a failing registry renders its step as not-done,
 * never as an error wall. The overview renders the "full" variant instead of
 * the control room on an empty tenant, and the "compact" variant above the
 * control room while onboarding is partially complete.
 */

export const ONBOARDING_ENDPOINTS = {
  connectors: "/demo/manufacturing/connectors",
  ontology: "/demo/manufacturing/ontology",
  policies: "/platform/policies",
  agents: "/demo/manufacturing/agents",
  workflows: "/demo/manufacturing/workflows",
} as const;

export type OnboardingStepId = keyof typeof ONBOARDING_ENDPOINTS;

/** "unknown" means the registry did not answer; rendered as not-done. */
export type OnboardingStepState = "done" | "todo" | "unknown";

export type OnboardingStep = {
  id: OnboardingStepId;
  title: string;
  why: string;
  cta: string;
  href: string;
  state: OnboardingStepState;
};

export type OnboardingChecklistProps = {
  /** "full" replaces the empty-tenant overview; "compact" tops the control room. */
  variant?: "full" | "compact";
  /** Wired by the demo-provisioning flow (task 6.3); absent means disabled. */
  onExploreDemo?: () => void;
  /** Enables the "Explore with demo data" CTA once the endpoint exists. */
  demoAvailable?: boolean;
};

const STEP_ROUTES: Record<OnboardingStepId, string> = {
  connectors: "/connectors",
  ontology: "/ontology",
  policies: "/policies",
  agents: "/agents",
  workflows: "/workflows",
};

function stepState(count: number | null): OnboardingStepState {
  if (count === null) {
    return "unknown";
  }
  return count > 0 ? "done" : "todo";
}

/**
 * Five best-effort registry queries — one per step, nothing else. Each
 * failing or pending query yields a null count and an "unknown" step.
 */
function useOnboardingSteps(): OnboardingStep[] {
  const connectors = useAxisQuery<ManufacturingConnectorRegistry>(ONBOARDING_ENDPOINTS.connectors);
  const ontology = useAxisQuery<ManufacturingOntology>(ONBOARDING_ENDPOINTS.ontology);
  const policies = useAxisQuery<PlatformPolicyRegistry>(ONBOARDING_ENDPOINTS.policies);
  const agents = useAxisQuery<ManufacturingAgentRegistry>(ONBOARDING_ENDPOINTS.agents);
  const workflows = useAxisQuery<ManufacturingWorkflowConsole>(ONBOARDING_ENDPOINTS.workflows);

  const counts: Record<OnboardingStepId, number | null> = {
    connectors: connectors.data ? connectors.data.connectors.length : null,
    ontology: ontology.data ? ontology.data.nodes.length : null,
    policies: policies.data ? policies.data.policy_count : null,
    agents: agents.data ? agents.data.agents.length : null,
    workflows: workflows.data ? workflows.data.workflow_runs.length : null,
  };

  return (Object.keys(ONBOARDING_ENDPOINTS) as OnboardingStepId[]).map((id) => ({
    id,
    title: strings.onboarding.steps[id].title,
    why: strings.onboarding.steps[id].why,
    cta: strings.onboarding.steps[id].cta,
    href: STEP_ROUTES[id],
    state: stepState(counts[id]),
  }));
}

function ProgressBar({ complete, total }: { complete: number; total: number }) {
  return (
    <div className="grid min-w-0 gap-1.5">
      <p className="m-0 text-sm font-medium text-ink">
        {complete} of {total} {strings.onboarding.stepsComplete}
      </p>
      <div
        aria-label={strings.onboarding.progressLabel}
        aria-valuemax={total}
        aria-valuemin={0}
        aria-valuenow={complete}
        className="h-1.5 w-full max-w-xs overflow-hidden rounded-full bg-ink/10 dark:bg-white/10"
        role="progressbar"
      >
        <div
          className="h-full rounded-full bg-signal transition-all duration-300"
          style={{ width: `${(complete / total) * 100}%` }}
        />
      </div>
    </div>
  );
}

function StepRow({ step }: { step: OnboardingStep }) {
  const done = step.state === "done";

  return (
    <li className="flex flex-wrap items-center gap-3 rounded-2xl border border-line px-4 py-3 dark:border-white/10">
      {done ? (
        <CircleCheckBig aria-hidden="true" className="shrink-0 text-positive" size={18} />
      ) : (
        <Circle aria-hidden="true" className="shrink-0 text-muted" size={18} />
      )}
      <div className="grid min-w-0 flex-1 gap-0.5">
        <p className={cn("m-0 text-sm font-medium break-words", done ? "text-muted" : "text-ink")}>
          {step.title}
        </p>
        <p className="m-0 text-xs text-muted">{step.why}</p>
      </div>
      {done ? (
        <span className="status-pill signal-ready">{strings.onboarding.stepDone}</span>
      ) : (
        <Link
          className={cn(
            "inline-flex items-center rounded-full border border-line px-3.5 py-1.5 text-xs font-medium",
            "text-ink transition-colors hover:border-signal/50 hover:text-signal dark:border-white/15",
          )}
          href={step.href}
        >
          {step.cta}
        </Link>
      )}
    </li>
  );
}

function StepList({ steps }: { steps: OnboardingStep[] }) {
  return (
    <ol className="m-0 grid list-none gap-2 p-0">
      {steps.map((step) => (
        <StepRow key={step.id} step={step} />
      ))}
    </ol>
  );
}

function ExploreDemoButton({
  onExploreDemo,
  demoAvailable,
}: Pick<OnboardingChecklistProps, "onExploreDemo" | "demoAvailable">) {
  const enabled = Boolean(demoAvailable && onExploreDemo);

  return (
    <Button
      className="px-5 py-2.5 text-sm"
      disabled={!enabled}
      onClick={enabled ? onExploreDemo : undefined}
      title={enabled ? undefined : strings.onboarding.exploreDemo.comingSoon}
      variant="secondary"
    >
      {strings.onboarding.exploreDemo.label}
    </Button>
  );
}

export function OnboardingChecklist({
  variant = "full",
  onExploreDemo,
  demoAvailable = false,
}: OnboardingChecklistProps) {
  const steps = useOnboardingSteps();
  const [stepsOpen, setStepsOpen] = useState(false);
  const total = steps.length;
  const complete = steps.filter((step) => step.state === "done").length;

  // Fully onboarded tenants never see the checklist; the compact strip also
  // stays away until at least one step is actually complete.
  if (complete === total || (variant === "compact" && complete === 0)) {
    return null;
  }

  if (variant === "compact") {
    const ToggleChevron = stepsOpen ? ChevronDown : ChevronRight;

    return (
      <Collapsible onOpenChange={setStepsOpen} open={stepsOpen}>
        <Card aria-label={strings.onboarding.eyebrow} className="grid gap-3 p-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="grid min-w-0 gap-1.5">
              <Eyebrow>{strings.onboarding.eyebrow}</Eyebrow>
              <ProgressBar complete={complete} total={total} />
            </div>
            <CollapsibleTrigger asChild>
              <button
                className="inline-flex cursor-pointer items-center gap-1 text-xs font-medium text-muted transition-colors hover:text-ink"
                type="button"
              >
                <ToggleChevron aria-hidden="true" size={13} />
                {stepsOpen ? strings.onboarding.compact.hide : strings.onboarding.compact.show}
              </button>
            </CollapsibleTrigger>
          </div>
          <CollapsibleContent>
            <StepList steps={steps} />
          </CollapsibleContent>
        </Card>
      </Collapsible>
    );
  }

  return (
    <Card aria-label={strings.onboarding.eyebrow} className="grid gap-4 p-6">
      <div className="grid gap-1">
        <Eyebrow>{strings.onboarding.eyebrow}</Eyebrow>
        <h2 className="font-display m-0 text-xl text-ink">{strings.onboarding.title}</h2>
        <p className="m-0 max-w-2xl text-sm leading-snug text-muted">
          {strings.onboarding.description}
        </p>
      </div>
      <ProgressBar complete={complete} total={total} />
      <StepList steps={steps} />
      <div className="flex flex-wrap items-center gap-3 border-t border-line/60 pt-4 dark:border-white/10">
        <ExploreDemoButton demoAvailable={demoAvailable} onExploreDemo={onExploreDemo} />
      </div>
    </Card>
  );
}
