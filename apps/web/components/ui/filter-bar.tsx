"use client";

import { RotateCcw } from "lucide-react";

import { Field } from "@/components/ui/field";
import { Select } from "@/components/ui/select";

export type FilterDef = {
  id: string;
  label: string;
  options: { value: string; label: string }[];
};

export interface FilterBarProps {
  filters: FilterDef[];
  values: Record<string, string>;
  onChange: (id: string, value: string) => void;
  onReset: () => void;
}

/** Consistent filter row for list pages: labelled selects + a visible Reset. */
export function FilterBar({ filters, values, onChange, onReset }: FilterBarProps) {
  return (
    <div aria-label="Filters" className="flex min-w-0 flex-wrap items-end gap-3" role="group">
      {filters.map((filter) => (
        <Field key={filter.id} className="w-44 max-w-full" label={filter.label}>
          <Select
            value={values[filter.id] ?? ""}
            onChange={(event) => onChange(filter.id, event.target.value)}
          >
            {filter.options.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </Select>
        </Field>
      ))}
      <button
        className="inline-flex min-h-[38px] cursor-pointer items-center gap-1.5 rounded-xl border border-transparent px-3 text-sm font-medium text-muted transition-colors duration-200 hover:border-line hover:text-signal dark:hover:border-white/15"
        type="button"
        onClick={onReset}
      >
        <RotateCcw aria-hidden="true" size={14} />
        Reset
      </button>
    </div>
  );
}
