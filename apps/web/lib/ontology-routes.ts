/** Build a detail route from one opaque ontology node-id path segment. */
export function buildOntologyEntityRoute(nodeId: string): string {
  return `/ontology/${encodeURIComponent(nodeId)}`;
}

/**
 * Convert the dynamic route segment back into the opaque node ID.
 *
 * Next preserves escaped path separators in dynamic params, so this decoding
 * belongs at the server route boundary. Decode exactly once: IDs containing a
 * literal percent escape (for example, `%2F`) must remain distinct from IDs
 * containing the corresponding character. A malformed escape is retained as
 * an opaque ID and will produce the normal not-found state instead of making
 * the page throw while rendering.
 */
export function decodeOntologyEntityRouteParam(nodeId: string): string {
  try {
    return decodeURIComponent(nodeId);
  } catch {
    return nodeId;
  }
}
