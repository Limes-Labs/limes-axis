"use client";

import {
  platformPolicyAutonomyLevels,
  platformPolicyRiskLevels,
  type PolicyConditionsFormState,
  type PolicyDraftFieldErrors,
} from "@/lib/platform-policies";

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
    <div aria-label={label} className="condition-group" role="group">
      <span className="metric-label">{label}</span>
      <div className="tag-list">
        {options.map((option) => (
          <button
            aria-pressed={selected.includes(option)}
            className="tag"
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
      <label className="field-wide">
        <span className="metric-label">Action Domains</span>
        <input
          aria-label={`${labelPrefix} action domains`}
          onChange={(event) => update({ actionDomainsText: event.target.value })}
          placeholder="Operations, Finance (comma separated)"
          type="text"
          value={conditions.actionDomainsText}
        />
      </label>
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
      <label>
        <span className="metric-label">Amount Threshold</span>
        <input
          aria-label={`${labelPrefix} amount threshold`}
          min="0"
          onChange={(event) => update({ requestedAmount: event.target.value })}
          placeholder="Optional"
          step="any"
          type="number"
          value={conditions.requestedAmount}
        />
      </label>
      {errors.requestedAmount ? (
        <p className="row-detail field-wide" role="alert">
          {errors.requestedAmount}
        </p>
      ) : null}
      {errors.conditions ? (
        <p className="row-detail field-wide" role="alert">
          {errors.conditions}
        </p>
      ) : null}
    </>
  );
}
