import type { AxisOperatorError } from "@/lib/axis-api";
import { useStrings } from "@/providers/locale-provider";

/**
 * Compact mutation failure for forms that already use inline status copy.
 * Only the display-safe operator projection is accepted, so response bodies
 * and arbitrary caught values cannot accidentally enter the rendered tree.
 */
export function InlineOperatorError({
  error,
  prefix,
}: {
  error: AxisOperatorError;
  prefix?: string;
}) {
  const strings = useStrings();
  return (
    <div className="grid gap-1" role="alert">
      <p className="mx-0 mt-1 mb-0 text-sm leading-snug text-danger break-words">
        {prefix ? `${prefix}: ` : ""}{error.message}
      </p>
      {error.requestId ? (
        <p className="m-0 text-xs leading-snug text-muted break-words">
          {strings.ui.uiInlineOperatorError.requestReference}{" "}<span className="font-mono text-ink">{error.requestId}</span>
        </p>
      ) : null}
    </div>
  );
}
