/*
 * Italian console copy. Typed against the English catalogue in
 * `lib/strings.ts` (the source of truth): every key and every template
 * function must exist here with the same signature, or typecheck fails.
 */
import type { ConsoleGlossary, ConsoleStrings } from "@/lib/i18n";
import { glossary, strings } from "@/lib/strings";

const nav = {
  operate: "Operatività",
  dataAndModels: "Dati e modelli",
  governance: "Governance",
  platform: "Piattaforma",
  help: "Assistenza",
  signedOut: "Accesso non effettuato",
  noTenant: "Nessun tenant selezionato",
} as const;

const pages = {
  overview: {
    eyebrow: nav.operate,
    title: "Panoramica",
    description:
      "Trasformi i dati aziendali collegati in azioni che il team può esaminare e monitorare.",
  },
  approvals: {
    eyebrow: nav.operate,
    title: "Approvazioni",
    description: "Esamini le azioni proposte e segua gli esiti segnalati.",
  },
  workflows: {
    eyebrow: nav.operate,
    title: "Workflow",
    description: "Monitori l'avanzamento dei workflow e risolva i blocchi.",
  },
  agents: {
    eyebrow: nav.operate,
    title: "Agenti",
    description: "Verifichi cosa può fare ciascun agente ed esamini le sue esecuzioni.",
  },
  ontology: {
    eyebrow: nav.dataAndModels,
    title: "Ontologia",
    description:
      "Esplori gli oggetti di business, come ordini e macchinari, e le loro relazioni.",
  },
  connectors: {
    eyebrow: nav.dataAndModels,
    title: "Connettori",
    description: "Colleghi le fonti dati e ne monitori le importazioni.",
  },
  data: {
    eyebrow: nav.dataAndModels,
    title: "Dati",
    description: "Trovi gli asset di dati, ne verifichi le evidenze e assegni la responsabilità.",
  },
  "model-routing": {
    eyebrow: nav.dataAndModels,
    title: "Modelli",
    description: "Esamini le regole di selezione dei modelli e le chiamate AI registrate.",
  },
  policies: {
    eyebrow: nav.governance,
    title: "Policy",
    description: "Definisca le regole per azioni, accesso ai dati e approvazione umana.",
  },
  audit: {
    eyebrow: nav.governance,
    title: "Audit",
    description: "Ricostruisca azioni, decisioni ed evidenze registrate.",
  },
  simulation: {
    eyebrow: nav.governance,
    title: "Simulazione",
    description: "Confronti gli esiti delle policy prima di applicare le modifiche.",
  },
  tenants: {
    eyebrow: nav.platform,
    title: "Tenant",
    description: "Gestisca le organizzazioni e i relativi limiti di risorse.",
  },
  settings: {
    eyebrow: nav.platform,
    title: "Impostazioni",
    description:
      "Verifichi che la piattaforma sia integra, connessa e pronta per il team.",
  },
} as const;

/*
 * Seed: the console chrome is translated; the remaining sections fall back to
 * English until the full catalogue lands.
 */
export const stringsIt: ConsoleStrings = {
  ...strings,
  nav,
  pages,
  shell: {
    ...strings.shell,
    theme: {
      trigger: "Tema colori",
      triggerLabel: (current: string) => `Tema colori: ${current}`,
      options: { system: "Sistema", light: "Chiaro", dark: "Scuro" },
    },
    locale: {
      label: "Lingua",
      detail: "La modifica della lingua ricarica la console.",
    },
  },
};

export const glossaryIt: ConsoleGlossary = { ...glossary };
