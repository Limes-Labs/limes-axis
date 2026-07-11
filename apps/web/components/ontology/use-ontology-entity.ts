"use client";

import { useEffect, useState } from "react";

import { axisFetch } from "@/lib/axis-api";
import type { ManufacturingOntologyEntityDetail } from "@/lib/ontology-demo";
import { useOidcConsoleSession } from "@/lib/use-oidc-session";
import { useConsole } from "@/providers/console-provider";

export type OntologyEntitySource = "loading" | "api" | "unavailable" | "missing";

type OntologyEntityResult = {
  nodeId: string;
  detail: ManufacturingOntologyEntityDetail | null;
  source: OntologyEntitySource;
};

/**
 * Fetch a single ontology entity detail from the Axis API. Shared by the
 * full entity page and the explorer slide-over; passing `null` keeps the
 * hook idle (nothing is fetched while the slide-over is closed).
 *
 * The result is keyed by node id, so switching entities reports "loading"
 * immediately instead of flashing the previous entity.
 */
export function useOntologyEntity(nodeId: string | null) {
  const [result, setResult] = useState<OntologyEntityResult | null>(null);
  const { session } = useOidcConsoleSession();
  const { refreshNonce } = useConsole();

  useEffect(() => {
    if (!nodeId) {
      return;
    }

    const controller = new AbortController();

    async function fetchEntity() {
      try {
        const response = await axisFetch(
          `/demo/manufacturing/ontology/entities/${encodeURIComponent(nodeId!)}`,
          {
            session,
            signal: controller.signal,
          },
        );

        if (response.status === 404) {
          setResult({ nodeId: nodeId!, detail: null, source: "missing" });
          return;
        }

        if (!response.ok) {
          throw new Error(`Ontology entity request failed with ${response.status}`);
        }

        const detail = (await response.json()) as ManufacturingOntologyEntityDetail;
        setResult({ nodeId: nodeId!, detail, source: "api" });
      } catch {
        if (!controller.signal.aborted) {
          setResult({ nodeId: nodeId!, detail: null, source: "unavailable" });
        }
      }
    }

    void fetchEntity();

    return () => controller.abort();
  }, [nodeId, session, refreshNonce]);

  if (!nodeId || result?.nodeId !== nodeId) {
    return { detail: null, source: "loading" as const };
  }

  return { detail: result.detail, source: result.source };
}
