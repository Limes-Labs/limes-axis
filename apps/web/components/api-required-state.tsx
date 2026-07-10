"use client";

import { ErrorPanel } from "@/components/ui/states";

type ApiRequiredStateProps = {
  detail: string;
  endpoint: string;
  title: string;
};

/**
 * Compatibility wrapper over the unified ErrorPanel. Existing pages keep
 * their props API; migrations replace usages with ErrorPanel directly, and
 * this file goes away once the last usage is gone (Phase 5).
 */
export function ApiRequiredState({ detail, endpoint, title }: ApiRequiredStateProps) {
  return <ErrorPanel detail={detail} endpoint={endpoint} title={title} />;
}
