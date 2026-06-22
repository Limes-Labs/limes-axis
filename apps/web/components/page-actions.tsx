"use client";

import { GitBranch, RefreshCw } from "lucide-react";

import { OidcSessionBridge } from "./oidc-session-bridge";

export function PageActions() {
  return (
    <div className="toolbar" aria-label="Page actions">
      <button className="icon-button" type="button" aria-label="Refresh state" title="Refresh state">
        <RefreshCw size={17} />
      </button>
      <OidcSessionBridge />
      <button className="command-button" type="button">
        <GitBranch size={17} />
        Foundation
      </button>
    </div>
  );
}
