import { GitBranch, RefreshCw } from "lucide-react";

export function PageActions() {
  return (
    <div className="toolbar" aria-label="Page actions">
      <button className="icon-button" type="button" aria-label="Refresh state" title="Refresh state">
        <RefreshCw size={17} />
      </button>
      <button className="command-button" type="button">
        <GitBranch size={17} />
        Foundation
      </button>
    </div>
  );
}
