/*
 * Centralized console copy — every new user-facing string lives here so pages
 * stay plain-first and copy stays consistent (and i18n-ready). Raw identifiers,
 * scopes and hashes never appear in this module: they belong in Inspect
 * drawers and secondary mono details.
 */

export interface GlossaryEntry {
  label: string;
  definition: string;
}

/** Plain-English definitions for platform terms, rendered by `<Term />` tooltips. */
export const glossary = {
  ontology: {
    label: "Ontology",
    definition:
      "The shared vocabulary of business objects — machines, orders, materials — that connects your data, agents, and policies. It keeps every system talking about the same things.",
  },
  autonomy_level: {
    label: "Autonomy level",
    definition:
      "How much an agent may do on its own. Lower levels only suggest actions for humans to carry out; higher levels can act directly, with policies and approvals still applying.",
  },
  egress: {
    label: "Egress",
    definition:
      "Data leaving the platform for an outside system or provider. Egress is blocked by default and only opens through an explicit policy.",
  },
  evidence: {
    label: "Evidence",
    definition:
      "The recorded proof behind a decision or action: who acted, what they saw, and which rules applied. Evidence is written to the audit ledger and cannot be edited afterwards.",
  },
  dry_run: {
    label: "Dry run",
    definition:
      "A rehearsal of an action that computes the outcome without changing anything. Use it to check what would happen before committing.",
  },
  replay: {
    label: "Replay",
    definition:
      "Re-running past decisions against a different set of policies to compare outcomes. Nothing in production changes during a replay.",
  },
  idempotency: {
    label: "Idempotency",
    definition:
      "A guarantee that repeating the same request has no additional effect. It makes retries safe after a timeout or network failure.",
  },
  connector_manifest: {
    label: "Connector manifest",
    definition:
      "The reviewed description of a connector: where its data comes from, how fields map to the ontology, and which rules govern each sync.",
  },
  policy_scope: {
    label: "Policy scope",
    definition:
      "The part of the platform a policy applies to — an entire tenant, a domain, or a specific type of action.",
  },
} satisfies Record<string, GlossaryEntry>;

export type GlossaryKey = keyof typeof glossary;

export interface PageStrings {
  eyebrow: string;
  title: string;
  description: string;
}

const nav = {
  operate: "Operate",
  dataAndModels: "Data & Models",
  governance: "Governance",
  platform: "Platform",
} as const;

/** Per-route header copy, keyed by route segment (`overview` for `/`). */
const pages = {
  overview: {
    eyebrow: nav.operate,
    title: "Overview",
    description:
      "See what needs your attention right now across approvals, workflows, and platform health.",
  },
  approvals: {
    eyebrow: nav.operate,
    title: "Approvals",
    description:
      "Review and decide on actions agents have proposed. Every decision is recorded as audit evidence.",
  },
  workflows: {
    eyebrow: nav.operate,
    title: "Workflows",
    description:
      "Follow governed workflow runs from start to finish and see exactly what is blocking them.",
  },
  agents: {
    eyebrow: nav.operate,
    title: "Agents",
    description:
      "See every registered agent, what it is allowed to do, and how its recent runs went.",
  },
  ontology: {
    eyebrow: nav.dataAndModels,
    title: "Ontology",
    description:
      "Browse the shared business vocabulary that connects your data, agents, and policies.",
  },
  connectors: {
    eyebrow: nav.dataAndModels,
    title: "Connectors",
    description:
      "Bring data in from files and external systems, with every sync governed and recorded.",
  },
  "model-routing": {
    eyebrow: nav.dataAndModels,
    title: "Models",
    description:
      "See which AI models the platform routes work to, and the calls it has actually made.",
  },
  policies: {
    eyebrow: nav.governance,
    title: "Policies",
    description:
      "Write and version the rules that decide what agents may do and when a human steps in.",
  },
  audit: {
    eyebrow: nav.governance,
    title: "Audit",
    description:
      "Search the tamper-evident record of everything that has happened on the platform.",
  },
  simulation: {
    eyebrow: nav.governance,
    title: "Simulation",
    description:
      "Replay past decisions against different policies to see what would change before you commit.",
  },
  tenants: {
    eyebrow: nav.platform,
    title: "Tenants",
    description:
      "Manage the organizations on this deployment and the resources each one can use.",
  },
  settings: {
    eyebrow: nav.platform,
    title: "Settings",
    description: "Check that the platform is healthy, connected, and ready for your team.",
  },
} satisfies Record<string, PageStrings>;

export type PageKey = keyof typeof pages;

export const strings = {
  nav,
  states: {
    loading: "Loading…",
    error: {
      title: "This data could not be loaded",
      detail: "The console could not reach the platform API. Check your connection and try again.",
      retry: "Try again",
    },
    empty: {
      title: "Nothing here yet",
      detail: "Records will appear here as soon as they exist.",
    },
  },
  pages,
} as const;
