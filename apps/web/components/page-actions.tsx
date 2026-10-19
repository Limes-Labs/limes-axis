"use client";

import { RefreshCw } from "lucide-react";

import { useConsole } from "@/providers/console-provider";
import { useStrings } from "@/providers/locale-provider";

export function PageActions() {
  const strings = useStrings();
  const { triggerRefresh } = useConsole();

  return (
    <div className="flex flex-wrap justify-end gap-2" aria-label={strings.ui.pageActions.pageActions}>
      <button
        className="icon-button"
        type="button"
        aria-label={strings.ui.common.refreshState}
        title={strings.ui.common.refreshState}
        onClick={triggerRefresh}
      >
        <RefreshCw size={17} />
      </button>
    </div>
  );
}