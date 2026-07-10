"use client";

import {
  platformPolicyAutonomyLevels,
  platformPolicyRiskLevels,
  type PolicyConditionsFormState,
  type PolicyDraftFieldErrors,
} from "@/lib/platform-policies";
import { Field } from "@/components/ui/field";
import { Input } from "@/components/ui/input";

type PolicyConditionFieldsProps = {
  conditions: PolicyConditionsFormState;
  onChange: (next: PolicyConditionsFormState) => void;
  errors: Pick<PolicyDraftFieldErrors, "conditions" | "requestedAmount">;
  labelPrefix: string;
};

function toggleValue(values: string[], value: string): string[] {
  return values.includes(value)
    ? values.filter((item) => item !== value)
    : [...values, value];
}

function ConditionToggleGroup({
  label,
  options,
  selected,
  onToggle,
}: {
  label: string;
  options: string[];
  selected: string[];
  onToggle: (value: string) => void;
}) {
  return (
    <div aria-label={label} className="col-span-full grid min-w-0 content-start gap-1.5" role="group">
      <span className="eyebrow m-0">{label}</span>
      <div className="flex min-w-0 flex-wrap gap-2">
        {options.map((option) => (
          <button
            aria-pressed={selected.includes(option)}
            className="inline-flex min-w-0 max-w-full items-center gap-1.5 rounded-full border border-line bg-surface px-3 py-1 font-mono text-xs text-muted break-words transition-colors enabled:cursor-pointer aria-pressed:border-signal aria-pressed:bg-signal/10 aria-pressed:text-signal dark:border-white/15 dark:bg-white/5"
            key={option}
            onClick={() => onToggle(option)}
            type="button"
          >
            {option}
          </button>
        ))}
      </div>
    </div>
  );
}

export function PolicyConditionFields({
  conditions,
  onChange,
  errors,
  labelPrefix,
}: PolicyConditionFieldsProps) {
  function update(patch: Partial<PolicyConditionsFormState>) {
    onChange({ ...conditions, ...patch });
  }

  return (
    <>
      <Field className="col-span-full" label="Action Domains">
        <Input
          aria-label={`${labelPrefix} action domains`}
          onChange={(event) => update({ actionDomainsText: event.target.value })}
          placeholder="Operations, Finance (comma separated)"
          type="text"
          value={conditions.actionDomainsText}
        />
      </Field>
      <ConditionToggleGroup
        label={`${labelPrefix} risk levels`}
        onToggle={(value) => update({ riskLevels: toggleValue(conditions.riskLevels, value) })}
        options={platformPolicyRiskLevels}
        selected={conditions.riskLevels}
      />
      <ConditionToggleGroup
        label={`${labelPrefix} autonomy levels`}
        onToggle={(value) =>
          update({ autonomyLevels: toggleValue(conditions.autonomyLevels, value) })
        }
        options={platformPolicyAutonomyLevels}
        selected={conditions.autonomyLevels}
      />
      <Field label="Amount Threshold">
        <Input
          aria-label={`${labelPrefix} amount threshold`}
          min="0"
          onChange={(event) => update({ requestedAmount: event.target.value })}
          placeholder="Optional"
          step="any"
          type="number"
          value={conditions.requestedAmount}
        />
      </Field>
      {errors.requestedAmount ? (
        <p className="mx-0 mt-1 mb-0 text-sm leading-snug text-danger break-words col-span-full" role="alert">
          {errors.requestedAmount}
        </p>
      ) : null}
      {errors.conditions ? (
        <p className="mx-0 mt-1 mb-0 text-sm leading-snug text-danger break-words col-span-full" role="alert">
          {errors.conditions}
        </p>
      ) : null}
    </>
  );
}
