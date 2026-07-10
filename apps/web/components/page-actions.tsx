"use client";

import { RefreshCw } from "lucide-react";

import { useConsole } from "@/providers/console-provider";

export function PageActions() {
  const { triggerRefresh } = useConsole();

  return (
    <div className="flex flex-wrap justify-end gap-2" aria-label="Page actions">
      <button
        className="icon-button"
        type="button"
        aria-label="Refresh state"
        title="Refresh state"
        onClick={triggerRefresh}
      >
        <RefreshCw size={17} />
      </button>
    </div>
  );
}