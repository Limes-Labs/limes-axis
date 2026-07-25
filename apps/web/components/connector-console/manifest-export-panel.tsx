"use client";

import { useState } from "react";
import { Clipboard, Download, FileJson, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Field } from "@/components/ui/field";
import { Textarea } from "@/components/ui/input";
import { useToast } from "@/components/ui/toast";
import {
  connectorRegistrationFileName,
  serializeConnectorRegistrationDocument,
  type ConnectorListEntry,
} from "@/lib/connectors-console";
import { strings } from "@/lib/strings";

function downloadRegistrationDocument(entry: ConnectorListEntry, json: string) {
  const blob = new Blob([json], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = connectorRegistrationFileName(entry);
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}

export function ManifestExportPanel({ entry }: { entry: ConnectorListEntry }) {
  const copy = strings.connectors.manifestExport;
  const { push } = useToast();
  const [open, setOpen] = useState(false);
  const json = serializeConnectorRegistrationDocument(entry);

  async function copyJson() {
    try {
      await navigator.clipboard.writeText(json);
      push({ title: copy.copied, tone: "positive" });
    } catch {
      push({ title: copy.copyFailed, tone: "danger" });
    }
  }

  if (!open) {
    return (
      <Button onClick={() => setOpen(true)} size="sm" variant="secondary">
        <FileJson aria-hidden="true" />
        {copy.action}
      </Button>
    );
  }

  return (
    <section className="col-span-full grid min-w-0 gap-3 rounded-xl border border-line bg-surface/70 p-4 dark:border-white/10 dark:bg-white/4">
      <div className="flex min-w-0 flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="m-0 text-sm font-medium text-ink">{copy.title}</h3>
          <p className="mx-0 mt-1 mb-0 text-sm text-muted">{copy.description}</p>
        </div>
        <Button aria-label={copy.close} onClick={() => setOpen(false)} size="sm" variant="ghost">
          <X aria-hidden="true" />
        </Button>
      </div>
      <Field label={copy.jsonLabel}>
        <Textarea className="min-h-56 font-mono text-xs" readOnly value={json} />
      </Field>
      <div className="flex flex-wrap justify-end gap-2">
        <Button onClick={() => void copyJson()} variant="secondary">
          <Clipboard aria-hidden="true" />
          {copy.copy}
        </Button>
        <Button onClick={() => downloadRegistrationDocument(entry, json)}>
          <Download aria-hidden="true" />
          {copy.download}
        </Button>
      </div>
    </section>
  );
}
