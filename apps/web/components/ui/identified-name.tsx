import { cn } from "@/lib/cn";
import { presentText } from "@/lib/display-names";

/**
 * A display name with its raw identifier kept secondary: in the `title`
 * tooltip always, and as a mono line underneath when `showId` is set. The
 * identifier is omitted when it would only repeat the name.
 */
export function IdentifiedName({
  name,
  id,
  showId = false,
  className,
}: {
  name: string;
  id?: string | null;
  showId?: boolean;
  className?: string;
}) {
  const identifier = presentText(id);
  const distinct = identifier !== null && identifier !== name;

  return (
    <span className={cn("min-w-0", className)} data-identifier={identifier ?? undefined}>
      <span title={distinct ? identifier : undefined}>{name}</span>
      {showId && distinct ? (
        <span className="block font-mono text-xs break-all text-muted">{identifier}</span>
      ) : null}
    </span>
  );
}
