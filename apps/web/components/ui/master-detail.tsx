import type { ReactNode } from "react";

/**
 * Shared list/detail layout: a narrow list rail beside a wide detail pane on
 * large screens, stacked vertically on mobile.
 */
export function MasterDetail({ list, detail }: { list: ReactNode; detail: ReactNode }) {
  return (
    <div className="grid min-w-0 items-start gap-4 lg:grid-cols-[minmax(280px,360px)_minmax(0,1fr)]">
      <div className="min-w-0">{list}</div>
      <div className="min-w-0">{detail}</div>
    </div>
  );
}
