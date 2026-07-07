"use client";

import {
  comparePolicyRevisions,
  type PlatformPolicyRecord,
  type PolicyRevisionDiff,
} from "@/lib/platform-policies";

function DiffValue({ diff }: { diff: PolicyRevisionDiff }) {
  if (diff.kind === "scalar") {
    return (
      <span className="row-detail">
        {diff.changed ? `${diff.base} → ${diff.target}` : diff.target}
      </span>
    );
  }

  if (diff.removed.length === 0 && diff.added.length === 0 && diff.unchanged.length === 0) {
    return (
      <span className="tag-list">
        <span className="tag">None</span>
      </span>
    );
  }

  return (
    <span className="tag-list">
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
        <span className="tag" key={`unchanged-${item}`}>
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
    <div className="stack">
      <p className="row-detail">
        Comparing r{base.revision_number} / {base.policy_version} against the current r
        {target.revision_number} / {target.policy_version}: {changedCount} of {diffs.length}{" "}
        fields changed. Removed values (−) were dropped by the current revision; added values
        (+) are new in it.
      </p>
      <div className="payload-grid">
        {diffs.map((diff) => (
          <div className="payload-row" key={diff.label}>
            <span>
              <span className="metric-label">{diff.label}</span>
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
