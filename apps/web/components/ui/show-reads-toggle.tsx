"use client";

import { strings } from "@/lib/strings";

/**
 * "Show reads" switch for audit activity feeds and charts. Every console page
 * visit writes read evidence (one /connectors visit writes three events), so
 * feeds default to state-changing events and this control opts back in. It
 * only changes what is displayed: the append-only ledger is untouched.
 */
export function ShowReadsToggle({
  checked,
  hiddenCount,
  onCheckedChange,
}: {
  checked: boolean;
  /** Read events currently filtered out of the view. */
  hiddenCount: number;
  onCheckedChange: (checked: boolean) => void;
}) {
  const copy = strings.audit.reads;

  return (
    <span className="inline-flex min-w-0 flex-wrap items-center gap-x-3 gap-y-1">
      <label className="inline-flex min-h-[38px] items-center gap-2 text-sm text-ink select-none">
        <input
          checked={checked}
          className="size-4 accent-[rgb(var(--signal))]"
          onChange={(event) => onCheckedChange(event.target.checked)}
          type="checkbox"
        />
        {copy.show}
      </label>
      {!checked && hiddenCount > 0 ? (
        <span className="text-xs text-muted" data-testid="hidden-read-count">
          {copy.hidden(hiddenCount)}
        </span>
      ) : null}
    </span>
  );
}
