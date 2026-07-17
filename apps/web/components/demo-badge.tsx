"use client";

import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import type { ManufacturingOverview } from "@/lib/platform-overview";
import { strings } from "@/lib/strings";
import { buildTenantScopedPath, DEMO_TENANT_ID } from "@/lib/tenant-scope";
import { parseManufacturingOverview } from "@/lib/runtime-contracts/overview";
import { useAxisQuery } from "@/lib/use-axis-query";

export const DEMO_BADGE_OVERVIEW_ENDPOINT = "/demo/manufacturing/overview";

/**
 * Topbar "Demo" pill (task 6.3): shown only when the tenant's overview
 * answers with a demo scenario — i.e. the demo bootstrap has run. Loading,
 * 404 (never bootstrapped), and errors all render nothing; the badge is an
 * annotation, never a state surface.
 */
export function DemoBadge({
  enabled = true,
  tenantId = DEMO_TENANT_ID,
}: {
  enabled?: boolean;
  tenantId?: string;
}) {
  const overview = useAxisQuery<ManufacturingOverview>(
    buildTenantScopedPath(DEMO_BADGE_OVERVIEW_ENDPOINT, tenantId),
    { enabled, expectedTenantId: tenantId, parse: parseManufacturingOverview },
  );

  if (!overview.data?.scenario) {
    return null;
  }

  return (
    <TooltipProvider delayDuration={150}>
      <Tooltip>
        <TooltipTrigger asChild>
          <span className="status-pill signal-watch cursor-help" tabIndex={0}>
            {strings.demoBadge.label}
          </span>
        </TooltipTrigger>
        <TooltipContent>{strings.demoBadge.tooltip}</TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}
