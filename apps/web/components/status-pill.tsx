import {
  platformStatusClass,
  platformStatusLabel,
  type PlatformStatus,
} from "@/lib/platform-overview";
import { useStrings } from "@/providers/locale-provider";

/** Pill for the API's ready / watch / action_required platform statuses. */
export function PlatformStatusPill({ status }: { status: PlatformStatus }) {
  const strings = useStrings();
  return (
    <span className={`status-pill ${platformStatusClass(status)}`}>
      {platformStatusLabel(status, strings)}
    </span>
  );
}
