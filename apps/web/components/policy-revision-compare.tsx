"use client";

import {
  comparePolicyRevisions,
  type PlatformPolicyRecord,
  type PolicyRevisionDiff,
} from "@/lib/platform-policies";

function DiffValue({ diff }: { diff: PolicyRevisionDiff }) {
  if (diff.kind === "scalar") {
    return (
      <span className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words">
        {diff.changed ? `${diff.base} → ${diff.target}` : diff.target}
      </span>
    );
  }

  if (diff.removed.length === 0 && diff.added.length === 0 && diff.unchanged.length === 0) {
    return (
      <span className="flex min-w-0 flex-wrap gap-2">
        <span className="inline-flex min-w-0 max-w-full items-center gap-1.5 rounded-full border border-line bg-surface px-3 py-1 font-mono text-xs text-muted break-words transition-colors enabled:cursor-pointer aria-pressed:border-signal aria-pressed:bg-signal/10 aria-pressed:text-signal dark:border-white/15 dark:bg-white/5">None</span>
      </span>
    );
  }

  return (
    <span className="flex min-w-0 flex-wrap gap-2">
      {diff.removed.map((item) => (
        <span className="status-pill signal-action-required" key={`removed-${item}`}>
          − {item}
        </span>
      ))}
      {diff.added.map((item) => (
        <span className="status-pill signal-ready" key={`added-${item}`}>
          + {item}
        </span>
      ))}
      {diff.unchanged.map((item) => (
        <span className="inline-flex min-w-0 max-w-full items-center gap-1.5 rounded-full border border-line bg-surface px-3 py-1 font-mono text-xs text-muted break-words transition-colors enabled:cursor-pointer aria-pressed:border-signal aria-pressed:bg-signal/10 aria-pressed:text-signal dark:border-white/15 dark:bg-white/5" key={`unchanged-${item}`}>
          {item}
        </span>
      ))}
    </span>
  );
}

export function PolicyRevisionCompare({
  base,
  target,
}: {
  base: PlatformPolicyRecord;
  target: PlatformPolicyRecord;
}) {
  const diffs = comparePolicyRevisions(base, target);
  const changedCount = diffs.filter((diff) => diff.changed).length;

  return (
    <div className="grid min-w-0 gap-2.5">
      <p className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words">
        Comparing r{base.revision_number} / {base.policy_version} against the current r
        {target.revision_number} / {target.policy_version}: {changedCount} of {diffs.length}{" "}
        fields changed. Removed values (−) were dropped by the current revision; added values
        (+) are new in it.
      </p>
      <div className="grid min-w-0 gap-2">
        {diffs.map((diff) => (
          <div className="grid min-w-0 grid-cols-1 items-start gap-1 border-t border-line/60 pt-2 first:border-t-0 first:pt-0 dark:border-white/10 sm:grid-cols-[minmax(120px,0.35fr)_minmax(0,1fr)] sm:gap-2.5" key={diff.label}>
            <span>
              <span className="eyebrow m-0">{diff.label}</span>
              <span
                className={`status-pill ${diff.changed ? "signal-watch" : "status-checking"}`}
              >
                {diff.changed ? "Changed" : "Unchanged"}
              </span>
            </span>
            <DiffValue diff={diff} />
          </div>
        ))}
      </div>
    </div>
  );
}
